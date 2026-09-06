from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, cast, func, or_, select
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
    TopicLanguageFacet,
    TopicProject,
    TopicResponse,
)
from app.core.config import get_settings
from app.db.models import CatalogRepository, ExternalEvidenceItem, RepositoryChangeEvent
from app.db.session import get_session
from app.services.evidence import utc
from app.services.project_brief import build_brief, evaluate_constraints, external_sources
from app.services.topics import (
    build_topic_predicate,
    cursor_predicate,
    decode_cursor,
    encode_cursor,
    extract_matched_terms,
    get_all_topics,
    get_topic_definition,
)

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
async def topics(session: Session) -> list[TopicResponse]:
    return await get_all_topics(session)


@router.get("/topics/{slug}", response_model=TopicDetail)
async def topic(
    slug: str,
    session: Session,
    q: str | None = Query(
        None, max_length=200, description="Optional text search within the topic"
    ),
    language: str | None = Query(None, max_length=100, description="Optional language filter"),
    sort: Literal["relevance", "stars", "updated"] = Query("relevance", description="Sort order"),
    cursor: str | None = Query(None, max_length=4096, description="Opaque pagination cursor"),
    limit: int = Query(30, ge=1, le=100, description="Page limit"),
) -> TopicDetail:
    topic_def = get_topic_definition(slug)
    if topic_def is None:
        raise HTTPException(404, "Topic not found")

    q_clean = q.strip() if q and q.strip() else None
    lang_clean = language.strip() if language and language.strip() else None
    position = decode_cursor(cursor, slug, q_clean, lang_clean, sort)

    base_topic_pred = build_topic_predicate(topic_def)

    if q_clean:
        literal_q = q_clean.replace("/", "//").replace("%", "/%").replace("_", "/_")
        search_pred = or_(
            CatalogRepository.full_name.ilike(f"%{literal_q}%", escape="/"),
            CatalogRepository.description.ilike(f"%{literal_q}%", escape="/"),
            cast(CatalogRepository.topics, String).ilike(f"%{literal_q}%", escape="/"),
        )
        topic_and_q_pred = and_(base_topic_pred, search_pred)
    else:
        topic_and_q_pred = base_topic_pred

    # Language facets computed from topic + q matches before language filter
    lang_stmt = (
        select(
            CatalogRepository.primary_language,
            func.count(CatalogRepository.github_id),
        )
        .where(
            CatalogRepository.archived.is_(False),
            CatalogRepository.is_fork.is_(False),
            topic_and_q_pred,
            CatalogRepository.primary_language.is_not(None),
            CatalogRepository.primary_language != "",
        )
        .group_by(CatalogRepository.primary_language)
        .order_by(
            func.count(CatalogRepository.github_id).desc(),
            CatalogRepository.primary_language.asc(),
        )
    )
    lang_rows = (await session.execute(lang_stmt)).all()
    languages = [TopicLanguageFacet(value=str(row[0]), count=int(row[1])) for row in lang_rows]

    # Total count after language filter
    if lang_clean:
        final_pred = and_(
            topic_and_q_pred,
            func.lower(CatalogRepository.primary_language) == lang_clean.lower(),
        )
    else:
        final_pred = topic_and_q_pred

    count_stmt = select(func.count(CatalogRepository.github_id)).where(
        CatalogRepository.archived.is_(False),
        CatalogRepository.is_fork.is_(False),
        final_pred,
    )
    total_count = int(await session.scalar(count_stmt) or 0)

    # Deterministic ordering with identity tie-breaker
    data_stmt = select(CatalogRepository).where(
        CatalogRepository.archived.is_(False),
        CatalogRepository.is_fork.is_(False),
        final_pred,
    )
    if sort == "stars":
        data_stmt = data_stmt.order_by(
            CatalogRepository.stars.desc(),
            CatalogRepository.github_id.asc(),
        )
    elif sort == "updated":
        data_stmt = data_stmt.order_by(
            CatalogRepository.pushed_at.desc().nullslast(),
            CatalogRepository.github_id.asc(),
        )
    else:  # relevance
        data_stmt = data_stmt.order_by(
            CatalogRepository.selection_score.desc(),
            CatalogRepository.stars.desc(),
            CatalogRepository.github_id.asc(),
        )

    if position is not None:
        data_stmt = data_stmt.where(cursor_predicate(position, sort))
    page_rows = (await session.scalars(data_stmt.limit(limit + 1))).all()
    rows = page_rows[:limit]
    projects = [
        TopicProject(
            github_id=repo.github_id,
            full_name=repo.full_name,
            description=repo.description,
            primary_language=repo.primary_language,
            matched_terms=extract_matched_terms(repo, topic_def),
            pushed_at=repo.pushed_at,
            stars=repo.stars,
        )
        for repo in rows
    ]

    if len(page_rows) > limit:
        next_cursor = encode_cursor(slug, q_clean, lang_clean, sort, rows[-1])
    else:
        next_cursor = None

    # Compute actual matching count for the topic metadata
    topic_count_stmt = select(func.count(CatalogRepository.github_id)).where(
        CatalogRepository.archived.is_(False),
        CatalogRepository.is_fork.is_(False),
        base_topic_pred,
    )
    topic_repo_count = int(await session.scalar(topic_count_stmt) or 0)

    topic_response = TopicResponse(
        slug=topic_def.slug,
        name=topic_def.name,
        description=topic_def.description,
        terms=topic_def.terms,
        parent_slug=topic_def.parent_slug,
        repository_count=topic_repo_count,
    )

    return TopicDetail(
        topic=topic_response,
        projects=projects,
        limit=limit,
        total_count=total_count,
        next_cursor=next_cursor,
        languages=languages,
        changes=[],
    )
