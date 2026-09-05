import base64
from datetime import UTC, datetime
import json
from typing import Any

import structlog
from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    QueryEmbeddingCache,
    RepositoryEmbedding,
    RepositorySearchDocument,
    ScoutAssessment,
)
from app.services.ai import AIProvider, get_ai_provider

log = structlog.get_logger()


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        return max(0, int(decoded))
    except Exception:
        return 0


async def get_or_create_query_embedding(
    session: AsyncSession,
    query: str,
    ai_provider: AIProvider,
    settings: Settings,
) -> list[float]:
    """Retrieve cached query embedding or compute and persist a new one."""
    if not ai_provider.semantic_available:
        return []
    normalized = query.strip().casefold()
    model = f"{settings.ai_embedding_version}:{settings.ai_embedding_model}"

    cached = await session.get(QueryEmbeddingCache, (normalized, model))
    if cached and len(cached.embedding) == settings.ai_embedding_dimension:
        return list(cached.embedding)

    embeddings = await ai_provider.embed_texts([normalized])
    if not embeddings or not embeddings[0]:
        return []

    vec = embeddings[0]
    stmt = (
        insert(QueryEmbeddingCache)
        .values(
            normalized_query=normalized,
            model=model,
            embedding=vec,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing()
    )
    await session.execute(stmt)
    await session.commit()
    return vec


def _apply_sql_filters(query_stmt: Any, filters: dict[str, Any] | None) -> Any:
    """Apply structured pre-filters directly in SQL before ranking."""
    if not filters:
        return query_stmt

    if filters.get("language"):
        query_stmt = query_stmt.where(
            CatalogRepository.primary_language.ilike(filters["language"])
        )
    if filters.get("license"):
        query_stmt = query_stmt.where(CatalogRepository.license.ilike(filters["license"]))
    if filters.get("tier"):
        query_stmt = query_stmt.where(CatalogRepository.tier == filters["tier"])
    if filters.get("min_stars") is not None:
        query_stmt = query_stmt.where(CatalogRepository.stars >= int(filters["min_stars"]))
    if filters.get("max_stars") is not None:
        query_stmt = query_stmt.where(CatalogRepository.stars <= int(filters["max_stars"]))
    if filters.get("scout_only"):
        query_stmt = query_stmt.where(CatalogRepository.scout_eligible.is_(True))
    if filters.get("directory_only"):
        query_stmt = query_stmt.where(CatalogRepository.is_directory.is_(True))
    return query_stmt


async def hybrid_search(
    session: AsyncSession,
    query: str,
    filters: dict[str, Any] | None = None,
    cursor: str | None = None,
    limit: int = 50,
    settings: Settings | None = None,
    ai_provider: AIProvider | None = None,
) -> dict[str, Any]:
    """Execute hybrid natural-language search combining PostgreSQL full-text/trigram lexical search

    and pgvector cosine similarity with Reciprocal-Rank Fusion (RRF).
    """
    cfg = settings or get_settings()
    provider = ai_provider or get_ai_provider(cfg)
    clean_query = query.strip()
    offset = decode_cursor(cursor)
    target_limit = min(max(limit, 1), 100)
    fetch_candidates = min(200, (offset + target_limit) * 2)

    lexical_ranks: dict[int, int] = {}
    vector_ranks: dict[int, int] = {}
    semantic_available = False

    # 1. Lexical Search Branch
    lexical_stmt = (
        select(CatalogRepository.github_id)
        .join(
            RepositorySearchDocument,
            RepositorySearchDocument.github_id == CatalogRepository.github_id,
        )
        .where(
            or_(
                RepositorySearchDocument.full_name.ilike(f"%{clean_query}%"),
                RepositorySearchDocument.description.ilike(f"%{clean_query}%"),
                RepositorySearchDocument.topics_text.ilike(f"%{clean_query}%"),
                RepositorySearchDocument.name.ilike(f"%{clean_query}%"),
            )
        )
    )
    lexical_stmt = _apply_sql_filters(lexical_stmt, filters)
    lexical_stmt = lexical_stmt.order_by(
        CatalogRepository.stars.desc(),
        CatalogRepository.pushed_at.desc().nullslast(),
    ).limit(fetch_candidates)

    lexical_ids = list((await session.scalars(lexical_stmt)).all())
    for rank, gid in enumerate(lexical_ids):
        lexical_ranks[gid] = rank + 1

    # 2. Semantic Vector Branch (pgvector)
    try:
        query_vector = await get_or_create_query_embedding(session, clean_query, provider, cfg)
        if query_vector:
            # Query vector embeddings with cosine distance
            # Check if pgvector is available
            vector_stmt = (
                select(CatalogRepository.github_id)
                .join(
                    RepositoryEmbedding,
                    RepositoryEmbedding.github_id == CatalogRepository.github_id,
                )
                .where(RepositoryEmbedding.embedding_version == cfg.ai_embedding_version)
                .where(RepositoryEmbedding.model == cfg.ai_embedding_model)
            )
            vector_stmt = _apply_sql_filters(vector_stmt, filters)

            # Order by cosine distance if pgvector supported, otherwise fallback
            try:
                vector_stmt = vector_stmt.order_by(
                    RepositoryEmbedding.embedding.cosine_distance(query_vector)
                ).limit(fetch_candidates)
                async with session.begin_nested():
                    vector_ids = list((await session.scalars(vector_stmt)).all())
                for rank, gid in enumerate(vector_ids):
                    vector_ranks[gid] = rank + 1
                if vector_ids:
                    semantic_available = True
            except Exception as vec_exc:
                log.debug("vector_order_fallback", error=str(vec_exc))
    except Exception as exc:
        log.warning("semantic_search_branch_unavailable", error=str(exc))

    # 3. Reciprocal-Rank Fusion (RRF)
    # RRF Score: sum(weight / (k + rank))
    k = cfg.search_rrf_k
    all_gids = set(lexical_ranks.keys()) | set(vector_ranks.keys())
    rrf_scores: dict[int, float] = {}

    w_lexical = 0.5 if semantic_available else 1.0
    w_vector = 0.5 if semantic_available else 0.0

    for gid in all_gids:
        score = 0.0
        if gid in lexical_ranks:
            score += w_lexical / (k + lexical_ranks[gid])
        if gid in vector_ranks:
            score += w_vector / (k + vector_ranks[gid])
        rrf_scores[gid] = score

    sorted_gids = sorted(all_gids, key=lambda gid: rrf_scores[gid], reverse=True)
    total_matches = len(sorted_gids)

    # Apply pagination window
    page_gids = sorted_gids[offset : offset + target_limit]

    # Fetch hydrated CatalogRepository details and Scout assessments for the page
    items: list[dict[str, Any]] = []
    if page_gids:
        records_stmt = (
            select(CatalogRepository, ScoutAssessment)
            .outerjoin(
                ScoutAssessment,
                (ScoutAssessment.github_id == CatalogRepository.github_id)
                & (ScoutAssessment.is_current.is_(True)),
            )
            .where(CatalogRepository.github_id.in_(page_gids))
        )
        records = (await session.execute(records_stmt)).all()
        by_id = {repo.github_id: (repo, scout) for repo, scout in records}

        for gid in page_gids:
            if gid in by_id:
                repo, scout = by_id[gid]
                items.append(
                    {
                        "github_id": repo.github_id,
                        "owner": repo.owner,
                        "name": repo.name,
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "primary_language": repo.primary_language,
                        "license": repo.license,
                        "stars": repo.stars,
                        "forks": repo.forks,
                        "watchers": repo.watchers,
                        "open_issues": repo.open_issues,
                        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
                        "created_at": repo.created_at.isoformat() if repo.created_at else None,
                        "tier": repo.tier,
                        "is_directory": repo.is_directory,
                        "is_deep": repo.is_deep,
                        "classification": repo.classification,
                        "topics": repo.topics or [],
                        "selection_score": repo.selection_score,
                        "promise_score": repo.promise_score,
                        "scout": {
                            "promise_score": scout.promise_score,
                            "why_it_surfaced": scout.why_it_surfaced,
                            "supporting_facts": scout.supporting_facts,
                            "risk_flags": scout.risk_flags,
                            "confidence": scout.confidence,
                        }
                        if scout
                        else None,
                        "search_rrf_score": round(rrf_scores.get(gid, 0.0), 5),
                    }
                )

    next_cursor = (
        encode_cursor(offset + target_limit)
        if (offset + target_limit) < total_matches
        else None
    )

    rationale = (
        f"Ranked via hybrid lexical full-text and semantic vector retrieval (RRF k={k})"
        if semantic_available
        else "Ranked via lexical keyword retrieval (semantic retrieval offline/degraded)"
    )

    return {
        "items": items,
        "next_cursor": next_cursor,
        "total_count": total_matches,
        "interpreted_filters": filters or {},
        "result_rationale": rationale,
        "evidence_freshness": datetime.now(UTC).isoformat(),
        "semantic_available": semantic_available,
    }
