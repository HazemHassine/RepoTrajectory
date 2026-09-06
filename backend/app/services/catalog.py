from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    Repository,
    RepositoryEmbedding,
    RepositorySearchDocument,
    RepositoryTopic,
)
from app.services.ai import AIProvider, get_ai_provider

log = structlog.get_logger()


async def sync_catalog_from_repository(
    session: AsyncSession,
    repo: Repository,
    readme_text: str = "",
) -> CatalogRepository:
    """Synchronize a hydrated Repository into the canonical CatalogRepository and SearchDocument."""
    now = datetime.now(UTC)

    # Fetch topics
    topic_rows = (
        await session.scalars(
            select(RepositoryTopic.topic).where(RepositoryTopic.repository_id == repo.id)
        )
    ).all()
    topics = sorted({str(t).strip().casefold() for t in topic_rows if str(t).strip()})
    readme_bounded = readme_text[:20000] if readme_text else ""
    readme_excerpt = readme_bounded[:500] if readme_bounded else None

    # Upsert CatalogRepository
    stmt = (
        insert(CatalogRepository)
        .values(
            github_id=repo.github_id,
            owner=repo.owner,
            name=repo.name,
            full_name=repo.full_name,
            description=repo.description,
            primary_language=repo.primary_language,
            license=repo.license,
            default_branch=repo.default_branch,
            stars=repo.stars,
            forks=repo.forks,
            watchers=repo.watchers,
            open_issues=repo.open_issues,
            created_at=repo.created_at,
            updated_at=repo.updated_at,
            pushed_at=repo.pushed_at,
            archived=repo.archived,
            is_fork=False,
            tier="deep",
            is_directory=True,
            is_deep=True,
            classification="software",
            classification_confidence=1.0,
            topics=topics,
            activity_score=50.0,
            popularity_score=min(100.0, repo.stars * 1.0),
            freshness_score=90.0,
            maintenance_score=75.0,
            selection_score=75.0,
            scout_eligible=True,
            content_hash=None,
            readme_excerpt=readme_excerpt,
            last_discovered_at=repo.created_at,
            last_observed_at=now,
            repository_id=repo.id,
            provenance={
                "source": "github_rest_hydrated",
                "observed_at": now.isoformat(),
            },
        )
        .on_conflict_do_update(
            index_elements=[CatalogRepository.github_id],
            set_={
                "description": repo.description,
                "primary_language": repo.primary_language,
                "license": repo.license,
                "stars": repo.stars,
                "forks": repo.forks,
                "watchers": repo.watchers,
                "open_issues": repo.open_issues,
                "updated_at": repo.updated_at,
                "pushed_at": repo.pushed_at,
                "archived": repo.archived,
                "topics": topics,
                "is_deep": True,
                "tier": "deep",
                "repository_id": repo.id,
                **({"readme_excerpt": readme_excerpt} if readme_text else {}),
                "last_observed_at": now,
            },
        )
        .returning(CatalogRepository)
    )
    catalog_repo = await session.scalar(stmt)
    if catalog_repo is None:
        catalog_repo = await session.get(CatalogRepository, repo.github_id)
        if catalog_repo is None:
            raise RuntimeError(f"Could not load or create catalog repository for {repo.full_name}")

    # Upsert RepositorySearchDocument
    doc_stmt = (
        insert(RepositorySearchDocument)
        .values(
            github_id=repo.github_id,
            full_name=repo.full_name,
            name=repo.name,
            owner=repo.owner,
            description=repo.description,
            topics_text=" ".join(topics),
            primary_language=repo.primary_language,
            license=repo.license,
            readme_text=readme_bounded,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[RepositorySearchDocument.github_id],
            set_={
                "description": repo.description,
                "topics_text": " ".join(topics),
                "primary_language": repo.primary_language,
                "license": repo.license,
                **({"readme_text": readme_bounded} if readme_text else {}),
                "updated_at": now,
            },
        )
    )
    await session.execute(doc_stmt)
    await session.commit()
    return catalog_repo


async def generate_catalog_embeddings(
    session: AsyncSession,
    limit: int = 100,
    settings: Settings | None = None,
    ai_provider: AIProvider | None = None,
) -> int:
    """Generate real, versioned embeddings for catalog repositories missing them."""
    cfg = settings or get_settings()
    provider = ai_provider or get_ai_provider(cfg)
    if not provider.semantic_available:
        return 0
    version = cfg.ai_embedding_version
    model = cfg.ai_embedding_model

    # Find catalog repositories without an embedding for this version
    stmt = (
        select(CatalogRepository)
        .outerjoin(
            RepositoryEmbedding,
            (RepositoryEmbedding.github_id == CatalogRepository.github_id)
            & (RepositoryEmbedding.embedding_version == version),
        )
        .where(RepositoryEmbedding.id.is_(None))
        .order_by(CatalogRepository.stars.desc())
        .limit(limit)
    )
    targets = list((await session.scalars(stmt)).all())
    if not targets:
        return 0

    texts: list[str] = []
    for repo in targets:
        topics_str = ", ".join(repo.topics or [])
        text = (
            f"Repository: {repo.full_name}\n"
            f"Description: {repo.description or 'None'}\n"
            f"Language: {repo.primary_language or 'Unknown'}\n"
            f"Topics: {topics_str or 'None'}\n"
            f"License: {repo.license or 'None'}"
        )
        texts.append(text)

    embeddings = await provider.embed_texts(texts)
    now = datetime.now(UTC)

    count = 0
    for repo, vec in zip(targets, embeddings, strict=False):
        if not vec:
            continue
        emb_stmt = (
            insert(RepositoryEmbedding)
            .values(
                github_id=repo.github_id,
                embedding_version=version,
                model=model,
                embedding=vec,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[
                    RepositoryEmbedding.github_id,
                    RepositoryEmbedding.embedding_version,
                ],
                set_={
                    "model": model,
                    "embedding": vec,
                    "updated_at": now,
                },
            )
        )
        await session.execute(emb_stmt)
        count += 1

    await session.commit()
    log.info("catalog_embeddings_generated", count=count, version=version)
    return count


async def sync_catalog_from_search(
    session: AsyncSession,
    items: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    now: datetime,
) -> None:
    """Publish bounded search metadata without requiring deep hydration or extra HTTP."""
    payloads = {item["id"]: item for item in items}
    rows = []
    for candidate in candidates:
        if not candidate["eligible"]:
            continue
        payload = payloads[candidate["github_id"]]
        if not payload.get("created_at") or not payload.get("updated_at"):
            continue
        license_data = payload.get("license")
        rows.append(
            {
                **{
                    key: candidate[key]
                    for key in (
                        "github_id",
                        "owner",
                        "name",
                        "full_name",
                        "description",
                        "primary_language",
                        "topics",
                        "classification",
                        "classification_confidence",
                        "rejection_reason",
                        "stars",
                        "forks",
                        "pushed_at",
                        "archived",
                        "is_fork",
                    )
                },
                "license": license_data.get("spdx_id") if isinstance(license_data, dict) else None,
                "default_branch": payload.get("default_branch") or "main",
                "created_at": datetime.fromisoformat(
                    str(payload["created_at"]).replace("Z", "+00:00")
                ),
                "updated_at": datetime.fromisoformat(
                    str(payload["updated_at"]).replace("Z", "+00:00")
                ),
                "last_discovered_at": now,
                "last_observed_at": now,
                "provenance": {"source": "github_search", "observed_at": now.isoformat()},
            }
        )
    if not rows:
        return
    stmt = insert(CatalogRepository).values(rows)
    # Preserve deep links, tier, ranking, original discovery time and README evidence.
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[CatalogRepository.github_id],
            set_={
                key: getattr(stmt.excluded, key)
                for key in rows[0]
                if key not in {"github_id", "created_at", "last_discovered_at", "provenance"}
            },
        )
    )
    documents = [
        {
            "github_id": row["github_id"],
            "full_name": row["full_name"],
            "owner": row["owner"],
            "name": row["name"],
            "description": row["description"],
            "topics_text": " ".join(str(topic) for topic in row["topics"]),
            "primary_language": row["primary_language"],
            "license": row["license"],
            "updated_at": now,
            "readme_text": "",
        }
        for row in rows
    ]
    doc_stmt = insert(RepositorySearchDocument).values(documents)
    await session.execute(
        doc_stmt.on_conflict_do_update(
            index_elements=[RepositorySearchDocument.github_id],
            set_={
                key: getattr(doc_stmt.excluded, key)
                for key in documents[0]
                if key not in {"github_id", "readme_text"}
            },
        )
    )
