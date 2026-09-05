from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.product_schemas import (
    BriefResponse,
    ChangeResponse,
    ChangesResponse,
    ComparedProject,
    CompareRequest,
    CompareResponse,
    EvidenceResponse,
    ExternalSourcesResponse,
    TopicDetail,
    TopicResponse,
)
from app.core.config import get_settings
from app.db.models import CatalogRepository, ExternalEvidenceItem, RepositoryChangeEvent
from app.db.session import get_session
from app.services.evidence import utc
from app.services.project_brief import build_brief, evaluate_constraints, external_sources
from app.services.topics import TOPICS, topic_projects

router = APIRouter(tags=["product"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def find_repository(session: AsyncSession, owner: str, name: str) -> CatalogRepository:
    repo = await session.scalar(
        select(CatalogRepository).where(
            func.lower(CatalogRepository.full_name) == f"{owner}/{name}".casefold(),
        )
    )
    if repo is None:
        raise HTTPException(404, "Repository not found in catalog")
    return repo


@router.get("/repositories/{owner}/{name}/brief", response_model=BriefResponse)
async def brief(owner: str, name: str, session: Session) -> BriefResponse:
    return await build_brief(session, await find_repository(session, owner, name))


@router.get("/repositories/{owner}/{name}/evidence", response_model=list[EvidenceResponse])
async def evidence(
    owner: str, name: str, session: Session, limit: int = Query(60, ge=1, le=100)
) -> list[EvidenceResponse]:
    repo = await find_repository(session, owner, name)
    rows = (
        await session.scalars(
            select(ExternalEvidenceItem)
            .where(
                ExternalEvidenceItem.github_id == repo.github_id,
            )
            .order_by(ExternalEvidenceItem.observed_at.desc())
            .limit(limit)
        )
    ).all()
    return [EvidenceResponse.model_validate(row) for row in rows]


@router.get("/repositories/{owner}/{name}/external-sources", response_model=ExternalSourcesResponse)
async def sources(owner: str, name: str, session: Session) -> ExternalSourcesResponse:
    repo = await find_repository(session, owner, name)
    return await external_sources(session, repo.github_id)


@router.get("/repositories/by-id/{github_id}/changes", response_model=ChangesResponse)
async def changes(
    github_id: int,
    session: Session,
    since: datetime | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> ChangesResponse:
    if await session.get(CatalogRepository, github_id) is None:
        raise HTTPException(404, "Repository no longer in catalog")
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().evidence_retention_days)
    rows = (
        await session.scalars(
            select(RepositoryChangeEvent)
            .where(
                RepositoryChangeEvent.github_id == github_id,
                RepositoryChangeEvent.occurred_at > (utc(since) if since else cutoff),
            )
            .order_by(RepositoryChangeEvent.occurred_at.desc(), RepositoryChangeEvent.id.desc())
            .limit(limit + 1)
        )
    ).all()
    return ChangesResponse(
        items=[ChangeResponse.model_validate(row) for row in rows[:limit]],
        retention_start=cutoff,
        truncated=len(rows) > limit,
    )


@router.post("/compare/context", response_model=CompareResponse)
async def compare(payload: CompareRequest, session: Session) -> CompareResponse:
    if len(set(payload.github_ids)) != len(payload.github_ids):
        raise HTTPException(422, "Select distinct repositories")
    projects = []
    for gid in payload.github_ids:
        repo = await session.get(CatalogRepository, gid)
        if repo is None:
            raise HTTPException(404, f"Repository ID {gid} not found")
        project = await build_brief(session, repo)
        projects.append(
            ComparedProject(
                brief=project,
                fit=evaluate_constraints(repo, project, payload.constraints),
            )
        )
    return CompareResponse(constraints=payload.constraints, projects=projects)


@router.get("/topics", response_model=list[TopicResponse])
async def topics() -> list[TopicResponse]:
    return TOPICS


@router.get("/topics/{slug}", response_model=TopicDetail)
async def topic(slug: str, session: Session) -> TopicDetail:
    config = next((topic for topic in TOPICS if topic.slug == slug), None)
    if config is None:
        raise HTTPException(404, "Topic not found")
    projects = await topic_projects(session, config)
    rows = (
        await session.scalars(
            select(RepositoryChangeEvent)
            .where(
                RepositoryChangeEvent.github_id.in_([project.github_id for project in projects]),
            )
            .order_by(RepositoryChangeEvent.occurred_at.desc())
            .limit(20)
        )
    ).all()
    return TopicDetail(
        topic=config,
        projects=projects,
        changes=[ChangeResponse.model_validate(row) for row in rows],
    )
