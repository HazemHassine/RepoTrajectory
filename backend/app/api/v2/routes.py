import base64
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.schemas import (
    CatalogRepositorySummary,
    CursorPaginationEnvelope,
    FacetCount,
    FacetsResponse,
    HealthV2Response,
    ScoutCardSummary,
    ScoutFeedItem,
    ScoutFeedResponse,
    SearchRequest,
    SearchResponse,
    UnifiedRepositoryProfile,
)
from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    Contributor,
    MetricSnapshot,
    PullRequest,
    Repository,
    RepositoryContributor,
    RepositorySearchDocument,
    RepositorySnapshot,
    ScoutAssessment,
)
from app.db.session import get_session
from app.services.ai import get_ai_provider
from app.services.search import decode_cursor, encode_cursor, hybrid_search

router = APIRouter(tags=["v2"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _build_lens_metrics(repo: CatalogRepository, lens: str, scout: ScoutAssessment | None) -> dict[str, Any]:
    if lens == "maintainer":
        return {
            "lens": "maintainer",
            "maintenance_score": repo.maintenance_score,
            "open_issues": repo.open_issues,
            "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
            "is_deep_hydrated": repo.is_deep,
            "risk_flags": scout.risk_flags if scout else [],
        }
    elif lens == "investor":
        return {
            "lens": "investor",
            "popularity_score": repo.popularity_score,
            "activity_score": repo.activity_score,
            "selection_score": repo.selection_score,
            "promise_score": repo.promise_score,
            "confidence": scout.confidence if scout else None,
            "why_it_surfaced": scout.why_it_surfaced if scout else None,
        }
    else:  # developer lens
        return {
            "lens": "developer",
            "primary_language": repo.primary_language,
            "license": repo.license,
            "classification": repo.classification,
            "topics": repo.topics or [],
            "default_branch": repo.default_branch,
            "stars": repo.stars,
            "forks": repo.forks,
        }


@router.get("/repositories", response_model=CursorPaginationEnvelope)
async def list_repositories(
    session: SessionDep,
    settings: SettingsDep,
    language: str | None = None,
    license: str | None = None,
    tier: str | None = None,
    directory_only: bool = True,
    min_stars: int | None = None,
    max_stars: int | None = None,
    lens: str = Query("developer", pattern="^(developer|maintainer|investor)$"),
    sort: str = Query("selection", pattern="^(selection|stars|pushed|promise|activity|growth|health|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> CursorPaginationEnvelope:
    offset = decode_cursor(cursor)
    stmt = (
        select(CatalogRepository, ScoutAssessment)
        .outerjoin(
            ScoutAssessment,
            (ScoutAssessment.github_id == CatalogRepository.github_id)
            & (ScoutAssessment.is_current.is_(True)),
        )
    )

    if directory_only and tier is None:
        stmt = stmt.where(CatalogRepository.is_directory.is_(True))
    elif tier:
        stmt = stmt.where(CatalogRepository.tier == tier)

    if language:
        stmt = stmt.where(CatalogRepository.primary_language.ilike(language))
    if license:
        stmt = stmt.where(CatalogRepository.license.ilike(license))
    if min_stars is not None:
        stmt = stmt.where(CatalogRepository.stars >= min_stars)
    if max_stars is not None:
        stmt = stmt.where(CatalogRepository.stars <= max_stars)

    # Sorting options
    if sort == "stars":
        stmt = stmt.order_by(
            CatalogRepository.stars.asc() if order == "asc" else CatalogRepository.stars.desc(),
            CatalogRepository.github_id,
        )
    elif sort == "pushed":
        stmt = stmt.order_by(
            CatalogRepository.pushed_at.asc().nullslast() if order == "asc" else CatalogRepository.pushed_at.desc().nullslast(),
            CatalogRepository.github_id,
        )
    elif sort == "promise":
        stmt = stmt.order_by(
            CatalogRepository.promise_score.asc().nullslast() if order == "asc" else CatalogRepository.promise_score.desc().nullslast(),
            CatalogRepository.github_id,
        )
    elif sort in {"activity", "growth"}:
        stmt = stmt.order_by(
            CatalogRepository.activity_score.asc() if order == "asc" else CatalogRepository.activity_score.desc(),
            CatalogRepository.github_id,
        )
    elif sort == "health":
        stmt = stmt.order_by(
            CatalogRepository.maintenance_score.asc() if order == "asc" else CatalogRepository.maintenance_score.desc(),
            CatalogRepository.github_id,
        )
    elif sort == "name":
        stmt = stmt.order_by(
            CatalogRepository.name.desc() if order == "desc" else CatalogRepository.name.asc(),
            CatalogRepository.github_id,
        )
    else:  # selection
        stmt = stmt.order_by(CatalogRepository.selection_score.desc(), CatalogRepository.stars.desc())

    # Count matching items (subquery or estimate)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = int(await session.scalar(count_stmt) or 0)

    # Fetch page
    rows = (await session.execute(stmt.offset(offset).limit(limit))).all()
    items: list[CatalogRepositorySummary] = []
    for repo, scout in rows:
        scout_card = (
            ScoutCardSummary(
                promise_score=scout.promise_score,
                quantitative_score=scout.quantitative_score,
                ai_score=scout.ai_score,
                confidence=scout.confidence,
                why_it_surfaced=scout.why_it_surfaced,
                supporting_facts=scout.supporting_facts,
                uncertainty=scout.uncertainty,
                risk_flags=scout.risk_flags,
                score_components=scout.score_components,
                model_identity=scout.model_identity,
                created_at=scout.created_at,
            )
            if scout
            else None
        )
        lens_metrics = _build_lens_metrics(repo, lens, scout)
        summary = CatalogRepositorySummary.model_validate(repo)
        summary.scout = scout_card
        summary.lens_metrics = lens_metrics
        items.append(summary)

    next_cursor = encode_cursor(offset + limit) if (offset + limit) < total_count else None
    return CursorPaginationEnvelope(
        items=items,
        next_cursor=next_cursor,
        total_count=total_count,
        lens=lens,
    )


@router.get("/repositories/{owner}/{repo}", response_model=UnifiedRepositoryProfile)
async def get_repository_profile(
    owner: str,
    repo: str,
    session: SessionDep,
) -> UnifiedRepositoryProfile:
    stmt = (
        select(CatalogRepository, ScoutAssessment)
        .outerjoin(
            ScoutAssessment,
            (ScoutAssessment.github_id == CatalogRepository.github_id)
            & (ScoutAssessment.is_current.is_(True)),
        )
        .where(
            CatalogRepository.owner.ilike(owner),
            CatalogRepository.name.ilike(repo),
        )
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise HTTPException(404, f"Repository {owner}/{repo} not found in catalog")

    catalog_repo, scout = row
    scout_card = (
        ScoutCardSummary(
            promise_score=scout.promise_score,
            quantitative_score=scout.quantitative_score,
            ai_score=scout.ai_score,
            confidence=scout.confidence,
            why_it_surfaced=scout.why_it_surfaced,
            supporting_facts=scout.supporting_facts,
            uncertainty=scout.uncertainty,
            risk_flags=scout.risk_flags,
            score_components=scout.score_components,
            model_identity=scout.model_identity,
            created_at=scout.created_at,
        )
        if scout
        else None
    )

    catalog_summary = CatalogRepositorySummary.model_validate(catalog_repo)
    catalog_summary.scout = scout_card

    deep_evidence: dict[str, Any] | None = None
    if catalog_repo.repository_id:
        hydrated_repo = await session.get(Repository, catalog_repo.repository_id)
        if hydrated_repo:
            latest_metric = await session.scalar(
                select(MetricSnapshot)
                .where(MetricSnapshot.repository_id == hydrated_repo.id)
                .order_by(MetricSnapshot.calculated_at.desc())
                .limit(1)
            )
            top_contributors = (
                await session.execute(
                    select(Contributor.login, RepositoryContributor.contributions, Contributor.avatar_url)
                    .join(RepositoryContributor, Contributor.id == RepositoryContributor.contributor_id)
                    .where(RepositoryContributor.repository_id == hydrated_repo.id)
                    .order_by(RepositoryContributor.contributions.desc())
                    .limit(15)
                )
            ).all()
            snapshots = (
                await session.scalars(
                    select(RepositorySnapshot)
                    .where(RepositorySnapshot.repository_id == hydrated_repo.id)
                    .order_by(RepositorySnapshot.captured_at.desc())
                    .limit(30)
                )
            ).all()

            deep_evidence = {
                "hydrated_id": hydrated_repo.id,
                "last_ingested_at": hydrated_repo.last_ingested_at.isoformat()
                if hydrated_repo.last_ingested_at
                else None,
                "metric": {
                    "momentum_score": latest_metric.momentum_score,
                    "health_score": latest_metric.health_score,
                    "bus_factor_risk": latest_metric.bus_factor_risk,
                    "components": latest_metric.components,
                    "calculated_at": latest_metric.calculated_at.isoformat(),
                }
                if latest_metric
                else None,
                "top_contributors": [
                    {"login": c.login, "contributions": c.contributions, "avatar_url": c.avatar_url}
                    for c in top_contributors
                ],
                "snapshot_history": [
                    {
                        "captured_at": s.captured_at.isoformat(),
                        "stars": s.stars,
                        "forks": s.forks,
                        "open_issues": s.open_issues,
                    }
                    for s in snapshots
                ],
            }

    return UnifiedRepositoryProfile(
        catalog=catalog_summary,
        scout=scout_card,
        deep_evidence=deep_evidence,
        provenance=catalog_repo.provenance or {},
        readme_excerpt=catalog_repo.readme_excerpt,
    )


@router.post("/search", response_model=SearchResponse)
async def search_repositories(
    payload: SearchRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> SearchResponse:
    result = await hybrid_search(
        session=session,
        query=payload.query,
        filters=payload.filters,
        cursor=payload.cursor,
        limit=payload.limit,
        settings=settings,
    )
    return SearchResponse(**result)


@router.get("/scout", response_model=ScoutFeedResponse)
async def scout_feed(
    session: SessionDep,
    language: str | None = None,
    min_promise: float = Query(50.0, ge=0.0, le=100.0),
    max_stars: int | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> ScoutFeedResponse:
    offset = decode_cursor(cursor)
    stmt = (
        select(CatalogRepository, ScoutAssessment)
        .join(
            ScoutAssessment,
            (ScoutAssessment.github_id == CatalogRepository.github_id)
            & (ScoutAssessment.is_current.is_(True)),
        )
        .where(
            CatalogRepository.scout_eligible.is_(True),
            ScoutAssessment.promise_score >= min_promise,
        )
    )

    if language:
        stmt = stmt.where(CatalogRepository.primary_language.ilike(language))
    if max_stars is not None:
        stmt = stmt.where(CatalogRepository.stars <= max_stars)

    stmt = stmt.order_by(ScoutAssessment.promise_score.desc(), CatalogRepository.pushed_at.desc().nullslast())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = int(await session.scalar(count_stmt) or 0)

    rows = (await session.execute(stmt.offset(offset).limit(limit))).all()
    items: list[ScoutFeedItem] = []
    for repo, scout in rows:
        items.append(
            ScoutFeedItem(
                github_id=repo.github_id,
                owner=repo.owner,
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description,
                primary_language=repo.primary_language,
                license=repo.license,
                stars=repo.stars,
                forks=repo.forks,
                pushed_at=repo.pushed_at,
                topics=repo.topics or [],
                promise_score=scout.promise_score,
                confidence=scout.confidence,
                why_it_surfaced=scout.why_it_surfaced,
                supporting_facts=scout.supporting_facts,
                uncertainty=scout.uncertainty,
                risk_flags=scout.risk_flags,
                score_components=scout.score_components,
            )
        )

    next_cursor = encode_cursor(offset + limit) if (offset + limit) < total_count else None
    return ScoutFeedResponse(
        items=items,
        next_cursor=next_cursor,
        total_count=total_count,
    )


@router.get("/facets", response_model=FacetsResponse)
async def get_facets(session: SessionDep) -> FacetsResponse:
    # 1. Languages
    lang_rows = (
        await session.execute(
            select(CatalogRepository.primary_language, func.count())
            .where(CatalogRepository.primary_language.is_not(None))
            .group_by(CatalogRepository.primary_language)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()
    languages = [FacetCount(name=str(name), count=int(count)) for name, count in lang_rows if name]

    # 2. Categories
    cat_rows = (
        await session.execute(
            select(CatalogRepository.classification, func.count())
            .where(CatalogRepository.classification.is_not(None))
            .group_by(CatalogRepository.classification)
            .order_by(func.count().desc())
        )
    ).all()
    categories = [FacetCount(name=str(name), count=int(count)) for name, count in cat_rows if name]

    # 3. Licenses
    lic_rows = (
        await session.execute(
            select(CatalogRepository.license, func.count())
            .where(CatalogRepository.license.is_not(None))
            .group_by(CatalogRepository.license)
            .order_by(func.count().desc())
            .limit(15)
        )
    ).all()
    licenses = [FacetCount(name=str(name), count=int(count)) for name, count in lic_rows if name]

    # 4. Evidence Levels
    tier_rows = (
        await session.execute(
            select(CatalogRepository.tier, func.count()).group_by(CatalogRepository.tier)
        )
    ).all()
    evidence_levels = {str(tier): int(count) for tier, count in tier_rows}

    # 5. Freshness counts
    now = datetime.now(UTC)
    fresh_7d = await session.scalar(
        select(func.count()).where(CatalogRepository.pushed_at >= now - timedelta(days=7))
    )
    fresh_30d = await session.scalar(
        select(func.count()).where(CatalogRepository.pushed_at >= now - timedelta(days=30))
    )
    fresh_90d = await session.scalar(
        select(func.count()).where(CatalogRepository.pushed_at >= now - timedelta(days=90))
    )

    return FacetsResponse(
        languages=languages,
        categories=categories,
        licenses=licenses,
        evidence_levels=evidence_levels,
        freshness_counts={
            "pushed_last_7d": int(fresh_7d or 0),
            "pushed_last_30d": int(fresh_30d or 0),
            "pushed_last_90d": int(fresh_90d or 0),
        },
    )


@router.get("/health", response_model=HealthV2Response)
async def health_v2(session: SessionDep, settings: SettingsDep) -> HealthV2Response:
    provider = get_ai_provider(settings)
    ai_status = await provider.health()

    dir_count = int(
        await session.scalar(
            select(func.count()).where(CatalogRepository.is_directory.is_(True))
        )
        or 0
    )
    cand_count = int(
        await session.scalar(select(func.count()).select_from(CatalogRepository)) or 0
    )
    deep_count = int(
        await session.scalar(select(func.count()).where(CatalogRepository.is_deep.is_(True)))
        or 0
    )

    degraded_features: list[str] = []
    if not ai_status.get("available"):
        degraded_features.append("Hosted AI embeddings & evaluation offline (fallback active)")

    return HealthV2Response(
        status="healthy" if not degraded_features else "degraded",
        ai_service=ai_status,
        database={
            "connected": True,
            "directory_members": dir_count,
            "candidate_members": cand_count,
            "deep_cohort_members": deep_count,
        },
        directory_count=dir_count,
        candidate_count=cand_count,
        deep_cohort_count=deep_count,
        degraded_features=degraded_features,
    )
