import asyncio
import hmac
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AdminAuditResponse, AdminLoginRequest, AdminSessionResponse
from app.core.admin_auth import (
    AdminSession,
    clear_admin_cookie,
    create_admin_session,
    login_rate_limiter,
    require_admin_configuration,
    require_admin_mutation,
    require_admin_session,
    set_admin_cookie,
    validate_admin_origin,
    verify_admin_password,
)
from app.core.config import Settings, get_settings
from app.db.models import (
    AdminAuditLog,
    Commit,
    Contributor,
    ExternalRepositoryActivity,
    IngestionJob,
    Issue,
    MetricSnapshot,
    PullRequest,
    Release,
    Repository,
    RepositoryCandidate,
    RepositorySnapshot,
)
from app.db.session import get_session
from app.services.admin import add_admin_audit
from app.services.collector import CollectorScheduler, collector_overview, enqueue_job
from app.services.discovery import reclassify_stored_candidates

router = APIRouter(prefix="/admin", tags=["administration"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[AdminSession, Depends(require_admin_session)]
AdminMutationDep = Annotated[AdminSession, Depends(require_admin_mutation)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _session_response(session: AdminSession) -> AdminSessionResponse:
    return AdminSessionResponse(
        username=session.username,
        csrf_token=session.csrf_token,
        issued_at=session.issued_at,
        expires_at=session.expires_at,
    )


@router.post("/auth/login", response_model=AdminSessionResponse)
async def login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> AdminSessionResponse:
    require_admin_configuration(settings)
    validate_admin_origin(request, settings)
    client_key = request.client.host if request.client else "unknown"
    await login_rate_limiter.check(client_key)

    username_valid = hmac.compare_digest(payload.username, settings.admin_username)
    password_valid = await asyncio.to_thread(
        verify_admin_password, payload.password, settings.admin_password_hash or ""
    )
    if not (username_valid and password_valid):
        await login_rate_limiter.failed(client_key)
        add_admin_audit(session, request, None, "admin.login", outcome="rejected")
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid admin credentials")

    await login_rate_limiter.succeeded(client_key)
    token, admin_session = create_admin_session(settings)
    set_admin_cookie(response, token, settings)
    add_admin_audit(session, request, admin_session, "admin.login", outcome="succeeded")
    await session.commit()
    return _session_response(admin_session)


@router.get("/auth/session", response_model=AdminSessionResponse)
async def current_session(admin: AdminDep, response: Response) -> AdminSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return _session_response(admin)


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    admin: AdminMutationDep,
    settings: SettingsDep,
) -> dict[str, str]:
    clear_admin_cookie(response, settings)
    add_admin_audit(session, request, admin, "admin.logout", outcome="succeeded")
    await session.commit()
    return {"status": "signed_out"}


@router.get("/summary")
async def admin_summary(
    session: SessionDep,
    _admin: AdminDep,
    settings: SettingsDep,
    response: Response,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    models = {
        "repositories": Repository,
        "candidates": RepositoryCandidate,
        "snapshots": RepositorySnapshot,
        "metrics": MetricSnapshot,
        "contributors": Contributor,
        "commits": Commit,
        "pull_requests": PullRequest,
        "issues": Issue,
        "releases": Release,
        "external_activity": ExternalRepositoryActivity,
    }
    row_counts = {
        name: int(await session.scalar(select(func.count()).select_from(model)) or 0)
        for name, model in models.items()
    }
    return {
        "as_of": datetime.now(UTC),
        "row_counts": row_counts,
        "collector": await collector_overview(session),
        "configuration": {
            "github_token_configured": bool(settings.github_token),
            "collector_enabled": settings.collector_enabled,
            "collector_poll_seconds": settings.collector_poll_seconds,
            "candidate_limit": settings.collector_candidate_limit,
            "active_limit": settings.collector_active_limit,
            "active_refresh_hours": settings.collector_active_refresh_hours,
            "discovery_languages": settings.discovery_language_list,
            "discovery_min_stars": settings.discovery_min_stars,
            "gh_archive_enabled": settings.gh_archive_enabled,
            "gh_archive_hours_back": settings.gh_archive_hours_back,
            "gh_archive_retention_days": settings.gh_archive_retention_days,
            "github_rate_limit_reserve": settings.github_rate_limit_reserve,
            "admin_session_hours": settings.admin_session_hours,
            "secure_cookies": settings.admin_secure_cookies,
        },
    }


@router.get("/audit", response_model=list[AdminAuditResponse])
async def audit_log(
    session: SessionDep,
    _admin: AdminDep,
    response: Response,
    limit: int = Query(100, ge=1, le=500),
) -> list[AdminAuditLog]:
    response.headers["Cache-Control"] = "no-store"
    return list(
        (
            await session.scalars(
                select(AdminAuditLog).order_by(AdminAuditLog.occurred_at.desc()).limit(limit)
            )
        ).all()
    )


@router.post("/commands/{command}")
async def run_command(
    command: str,
    request: Request,
    session: SessionDep,
    admin: AdminMutationDep,
) -> dict[str, Any]:
    allowed = {"schedule", "reconcile", "maintenance", "reclassify"}
    if command not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown administrative command")

    try:
        if command == "schedule":
            result: dict[str, Any] = await CollectorScheduler().tick(session)
        elif command == "reclassify":
            result = await reclassify_stored_candidates(session)
        else:
            now = datetime.now(UTC)
            job_type = "reconcile_collection" if command == "reconcile" else "maintenance"
            job_id = await enqueue_job(
                session,
                job_type,
                f"admin:{job_type}:{now:%Y-%m-%d-%H%M%S-%f}",
                priority=250 if command == "reconcile" else 150,
                max_attempts=3,
            )
            result = {"job_id": job_id, "status": "queued"}
        add_admin_audit(
            session,
            request,
            admin,
            f"command.{command}",
            outcome="accepted",
            details=result,
        )
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        add_admin_audit(session, request, admin, f"command.{command}", outcome="failed")
        await session.commit()
        raise


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminMutationDep,
) -> dict[str, Any]:
    job = await session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Collector job not found")
    if job.status not in {"queued", "failed"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only queued or failed jobs can be cancelled"
        )
    now = datetime.now(UTC)
    cancel_result = await session.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job_id, IngestionJob.status.in_(["queued", "failed"]))
        .values(status="cancelled", finished_at=now, updated_at=now, locked_at=None, locked_by=None)
    )
    if not int(getattr(cancel_result, "rowcount", 0) or 0):
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Job state changed before it could be cancelled"
        )
    add_admin_audit(
        session,
        request,
        admin,
        "job.cancel",
        target=str(job_id),
        details={"job_type": job.job_type},
    )
    await session.commit()
    return {"job_id": job_id, "status": "cancelled"}
