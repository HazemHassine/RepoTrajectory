from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ActivityPoint,
    CandidateResponse,
    CollectionResponse,
    CollectorOverviewResponse,
    ContributorResponse,
    HistoryPoint,
    IngestionJobResponse,
    MetricResponse,
    QueueRepositoryRequest,
    RepositorySummary,
)
from app.core.admin_auth import AdminSession, require_admin_mutation, require_admin_session
from app.db.models import (
    Collection,
    CollectionMembership,
    Commit,
    Contributor,
    IngestionJob,
    Issue,
    MetricSnapshot,
    PullRequest,
    Release,
    Repository,
    RepositoryCandidate,
    RepositoryContributor,
    RepositorySnapshot,
)
from app.db.session import get_session
from app.services.admin import add_admin_audit
from app.services.analytics import calculate_metrics
from app.services.collector import CollectorScheduler, collector_overview, enqueue_job

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[AdminSession, Depends(require_admin_session)]
AdminMutationDep = Annotated[AdminSession, Depends(require_admin_mutation)]


async def find_repo(owner: str, repo: str, session: AsyncSession) -> Repository:
    value = await session.scalar(
        select(Repository).where(Repository.owner == owner, Repository.name == repo)
    )
    if not value:
        raise HTTPException(404, "Repository has not been ingested")
    return value


@router.get("/repositories", response_model=list[RepositorySummary], tags=["repositories"])
async def repositories(
    session: SessionDep,
    search: str | None = None,
    tier: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, le=500),
) -> list[Repository]:
    stmt = select(Repository).order_by(Repository.stars.desc()).offset(offset).limit(limit)
    if search:
        stmt = stmt.where(Repository.full_name.ilike(f"%{search}%"))
    if tier:
        stmt = stmt.join(
            RepositoryCandidate, RepositoryCandidate.repository_id == Repository.id
        ).where(RepositoryCandidate.tier == tier)
    return list((await session.scalars(stmt)).all())


@router.get("/repositories/{owner}/{repo}", response_model=RepositorySummary, tags=["repositories"])
async def repository(owner: str, repo: str, session: SessionDep) -> Repository:
    return await find_repo(owner, repo, session)


@router.get(
    "/repositories/{owner}/{repo}/metrics", response_model=MetricResponse, tags=["analytics"]
)
async def metrics(
    owner: str,
    repo: str,
    session: SessionDep,
    refresh: bool = False,
    window: int = Query(30, ge=7, le=365),
) -> MetricResponse:
    repository = await find_repo(owner, repo, session)
    metric = (
        None
        if refresh
        else await session.scalar(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.repository_id == repository.id, MetricSnapshot.window_days == window
            )
            .order_by(MetricSnapshot.calculated_at.desc())
            .limit(1)
        )
    )
    if (
        not metric
        or metric.components.get("methodology_version") != 3
        or (repository.last_ingested_at and metric.calculated_at < repository.last_ingested_at)
    ):
        metric = await calculate_metrics(session, repository, window)
    return MetricResponse(
        repository=repository.full_name,
        calculated_at=metric.calculated_at,
        window_days=metric.window_days,
        momentum_score=metric.momentum_score,
        health_score=metric.health_score,
        bus_factor_risk=metric.bus_factor_risk,
        components=metric.components,
    )


@router.get(
    "/repositories/{owner}/{repo}/history", response_model=list[HistoryPoint], tags=["analytics"]
)
async def history(
    owner: str,
    repo: str,
    session: SessionDep,
    days: int = Query(365, le=3650),
) -> list[RepositorySnapshot]:
    repository = await find_repo(owner, repo, session)
    return list(
        (
            await session.scalars(
                select(RepositorySnapshot)
                .where(
                    RepositorySnapshot.repository_id == repository.id,
                    RepositorySnapshot.captured_at >= datetime.now(UTC) - timedelta(days=days),
                )
                .order_by(RepositorySnapshot.captured_at)
            )
        ).all()
    )


@router.get(
    "/repositories/{owner}/{repo}/contributors",
    response_model=list[ContributorResponse],
    tags=["analytics"],
)
async def contributors(
    owner: str,
    repo: str,
    session: SessionDep,
    limit: int = Query(25, le=100),
) -> list[ContributorResponse]:
    repository = await find_repo(owner, repo, session)
    rows = (
        await session.execute(
            select(Contributor.login, RepositoryContributor.contributions, Contributor.avatar_url)
            .join(RepositoryContributor, Contributor.id == RepositoryContributor.contributor_id)
            .where(RepositoryContributor.repository_id == repository.id)
            .order_by(RepositoryContributor.contributions.desc())
            .limit(limit)
        )
    ).all()
    return [
        ContributorResponse(login=x.login, contributions=x.contributions, avatar_url=x.avatar_url)
        for x in rows
    ]


@router.get(
    "/repositories/{owner}/{repo}/activity", response_model=list[ActivityPoint], tags=["analytics"]
)
async def activity(
    owner: str,
    repo: str,
    session: SessionDep,
    weeks: int = Query(12, ge=1, le=104),
) -> list[ActivityPoint]:
    repository = await find_repo(owner, repo, session)
    now = datetime.now(UTC)
    current_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = current_week - timedelta(weeks=weeks - 1)

    async def grouped(model: Any, column: Any, *conditions: Any) -> dict[datetime, int]:
        period = func.date_trunc("week", column).label("period")
        rows = (
            await session.execute(
                select(period, func.count())
                .select_from(model)
                .where(model.repository_id == repository.id, column >= start, *conditions)
                .group_by(period)
            )
        ).all()
        return {row.period: int(row[1]) for row in rows}

    normalized_author = func.lower(func.coalesce(Commit.author_login, ""))
    human_commits = await grouped(
        Commit,
        Commit.committed_at,
        ~normalized_author.like("%[bot]"),
        ~normalized_author.in_(
            ["dependabot", "dependabot-preview", "github-actions", "pre-commit-ci"]
        ),
    )
    merged_prs = await grouped(PullRequest, PullRequest.merged_at)
    issues_closed = await grouped(Issue, Issue.closed_at)
    releases = await grouped(
        Release,
        Release.published_at,
        Release.draft.is_(False),
        Release.prerelease.is_(False),
    )
    return [
        ActivityPoint(
            period=period,
            commits=human_commits.get(period, 0),
            merged_prs=merged_prs.get(period, 0),
            issues_closed=issues_closed.get(period, 0),
            releases=releases.get(period, 0),
        )
        for period in (start + timedelta(weeks=offset) for offset in range(weeks))
    ]


@router.get("/rankings/{ranking}", response_model=list[MetricResponse], tags=["rankings"])
async def rankings(
    ranking: str,
    session: SessionDep,
    limit: int = Query(100, le=500),
    window: int = Query(30, ge=7, le=365),
) -> list[MetricResponse]:
    columns = {
        "momentum": MetricSnapshot.momentum_score,
        "health": MetricSnapshot.health_score,
        "risk": MetricSnapshot.bus_factor_risk,
    }
    if ranking not in columns:
        raise HTTPException(400, "ranking must be momentum, health, or risk")
    latest = (
        select(MetricSnapshot.repository_id, func.max(MetricSnapshot.calculated_at).label("latest"))
        .where(MetricSnapshot.window_days == window)
        .group_by(MetricSnapshot.repository_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(MetricSnapshot, Repository)
            .join(
                latest,
                (MetricSnapshot.repository_id == latest.c.repository_id)
                & (MetricSnapshot.calculated_at == latest.c.latest),
            )
            .join(Repository)
            .order_by(columns[ranking].desc())
            .limit(limit)
        )
    ).all()
    result: list[MetricResponse] = []
    for metric, repository in rows:
        # Metrics created by an older application version are refreshed lazily so existing
        # installations immediately gain new explainability components after an upgrade.
        if metric.components.get("methodology_version") != 3 or (
            repository.last_ingested_at and metric.calculated_at < repository.last_ingested_at
        ):
            metric = await calculate_metrics(session, repository, metric.window_days)
        result.append(
            MetricResponse(
                repository=repository.full_name,
                calculated_at=metric.calculated_at,
                window_days=metric.window_days,
                momentum_score=metric.momentum_score,
                health_score=metric.health_score,
                bus_factor_risk=metric.bus_factor_risk,
                components=metric.components,
            )
        )
    score_fields = {
        "momentum": lambda item: item.momentum_score or 0,
        "health": lambda item: item.health_score or 0,
        "risk": lambda item: item.bus_factor_risk or 0,
    }
    result.sort(key=score_fields[ranking], reverse=True)
    return result


@router.get("/collections", response_model=list[CollectionResponse], tags=["collection operations"])
async def collections(session: SessionDep) -> list[CollectionResponse]:
    counts = (
        select(
            CollectionMembership.collection_id.label("collection_id"),
            func.count().label("candidate_count"),
            func.count().filter(CollectionMembership.selected.is_(True)).label("selected_count"),
        )
        .group_by(CollectionMembership.collection_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                Collection,
                func.coalesce(counts.c.candidate_count, 0),
                func.coalesce(counts.c.selected_count, 0),
            )
            .outerjoin(counts, counts.c.collection_id == Collection.id)
            .order_by(Collection.name)
        )
    ).all()
    return [
        CollectionResponse(
            id=collection.id,
            slug=collection.slug,
            name=collection.name,
            description=collection.description,
            candidate_limit=collection.candidate_limit,
            active_limit=collection.active_limit,
            refresh_hours=collection.refresh_hours,
            enabled=collection.enabled,
            candidate_count=int(candidate_count),
            selected_count=int(selected_count),
            updated_at=collection.updated_at,
        )
        for collection, candidate_count, selected_count in rows
    ]


@router.get("/candidates", response_model=list[CandidateResponse], tags=["collection operations"])
async def candidates(
    session: SessionDep,
    tier: str | None = None,
    language: str | None = None,
    classification: str | None = None,
    search: str | None = None,
    eligible: bool | None = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[RepositoryCandidate]:
    stmt = (
        select(RepositoryCandidate)
        .order_by(RepositoryCandidate.trend_score.desc(), RepositoryCandidate.stars.desc())
        .offset(offset)
        .limit(limit)
    )
    if eligible is not None:
        stmt = stmt.where(RepositoryCandidate.eligible.is_(eligible))
    if tier:
        stmt = stmt.where(RepositoryCandidate.tier == tier)
    if language:
        stmt = stmt.where(RepositoryCandidate.primary_language == language)
    if classification:
        stmt = stmt.where(RepositoryCandidate.classification == classification)
    if search:
        stmt = stmt.where(RepositoryCandidate.full_name.ilike(f"%{search}%"))
    return list((await session.scalars(stmt)).all())


@router.get("/trending", response_model=list[CandidateResponse], tags=["collection operations"])
async def trending(
    session: SessionDep,
    limit: int = Query(100, ge=1, le=500),
) -> list[RepositoryCandidate]:
    return list(
        (
            await session.scalars(
                select(RepositoryCandidate)
                .where(
                    RepositoryCandidate.eligible.is_(True),
                    RepositoryCandidate.tier.in_(["active", "pinned"]),
                )
                .order_by(RepositoryCandidate.trend_score.desc())
                .limit(limit)
            )
        ).all()
    )


@router.get(
    "/collector/overview",
    response_model=CollectorOverviewResponse,
    tags=["collection operations"],
)
async def collector_status(session: SessionDep) -> dict[str, Any]:
    return await collector_overview(session)


@router.get(
    "/collector/jobs",
    response_model=list[IngestionJobResponse],
    tags=["collection operations"],
)
async def collector_jobs(
    session: SessionDep,
    _admin: AdminDep,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=250),
) -> list[IngestionJob]:
    stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(IngestionJob.status == status)
    return list((await session.scalars(stmt)).all())


@router.post("/collector/schedule", tags=["collection operations"])
async def run_collector_schedule(
    request: Request,
    session: SessionDep,
    admin: AdminMutationDep,
) -> dict[str, int]:
    result = await CollectorScheduler().tick(session)
    add_admin_audit(session, request, admin, "collector.schedule", details=result)
    await session.commit()
    return result


@router.post("/collector/repositories", tags=["collection operations"])
async def queue_repository(
    payload: QueueRepositoryRequest,
    request: Request,
    session: SessionDep,
    admin: AdminMutationDep,
) -> dict[str, Any]:
    bucket = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")
    job_id = await enqueue_job(
        session,
        "ingest_repository",
        f"manual:{payload.full_name.casefold()}:{bucket}",
        payload={"full_name": payload.full_name},
        priority=200,
    )
    add_admin_audit(
        session,
        request,
        admin,
        "repository.enqueue",
        target=payload.full_name,
        details={"job_id": job_id},
    )
    await session.commit()
    return {"job_id": job_id, "status": "queued"}


@router.post("/collector/jobs/{job_id}/retry", tags=["collection operations"])
async def retry_collector_job(
    job_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminMutationDep,
) -> dict[str, Any]:
    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(404, "collector job not found")
    if job.status not in {"failed", "cancelled"}:
        raise HTTPException(409, "only failed or cancelled jobs can be retried")
    now = datetime.now(UTC)
    retry_result = await session.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job_id, IngestionJob.status.in_(["failed", "cancelled"]))
        .values(
            status="queued",
            scheduled_for=now,
            attempts=0,
            finished_at=None,
            last_error=None,
            updated_at=now,
        )
    )
    if not int(getattr(retry_result, "rowcount", 0) or 0):
        await session.rollback()
        raise HTTPException(409, "job state changed before it could be retried")
    add_admin_audit(
        session,
        request,
        admin,
        "job.retry",
        target=str(job_id),
        details={"job_type": job.job_type},
    )
    await session.commit()
    return {"job_id": job_id, "status": "queued"}
