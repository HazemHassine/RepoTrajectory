import asyncio
import os
import socket
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import Integer, case, cast, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    CollectorState,
    ExternalRepositoryActivity,
    GhArchiveFile,
    IngestionJob,
    RepositoryCandidate,
    RepositoryEmbedding,
    ScoutAssessment,
)
from app.db.session import SessionLocal
from app.github.client import GitHubAPIError, GitHubClient, GitHubRateLimitError
from app.services.analytics import calculate_metrics
from app.services.catalog import generate_catalog_embeddings, sync_catalog_from_repository
from app.services.directory import discover_github_sharded, reconcile_directory_and_cohort
from app.services.discovery import (
    SOFTWARE_CLASSIFICATIONS,
    GhArchiveClient,
    backfill_existing_repositories,
    discover_github_repositories,
    ensure_default_collection,
    persist_gh_archive_hour,
    probe_repository_candidate,
    reconcile_collection,
)
from app.services.evidence import collect_repository_evidence, prune_evidence
from app.services.ingestion import RepositoryIngester
from app.services.scout import run_daily_scout_batch

log = structlog.get_logger()


async def enqueue_job(
    session: AsyncSession,
    job_type: str,
    dedupe_key: str,
    *,
    payload: dict[str, Any] | None = None,
    candidate_id: int | None = None,
    repository_id: int | None = None,
    collection_id: int | None = None,
    priority: int = 0,
    scheduled_for: datetime | None = None,
    max_attempts: int = 5,
) -> int:
    now = datetime.now(UTC)
    statement = (
        insert(IngestionJob)
        .values(
            job_type=job_type,
            status="queued",
            candidate_id=candidate_id,
            repository_id=repository_id,
            collection_id=collection_id,
            priority=priority,
            scheduled_for=scheduled_for or now,
            attempts=0,
            max_attempts=max_attempts,
            payload=payload or {},
            dedupe_key=dedupe_key,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=[IngestionJob.dedupe_key])
        .returning(IngestionJob.id)
    )
    job_id = await session.scalar(statement)
    if job_id is None:
        existing = await session.scalar(
            select(IngestionJob).where(IngestionJob.dedupe_key == dedupe_key)
        )
        if existing is not None and existing.status == "cancelled":
            existing.status = "queued"
            existing.candidate_id = candidate_id
            existing.repository_id = repository_id
            existing.collection_id = collection_id
            existing.priority = priority
            existing.scheduled_for = scheduled_for or now
            existing.attempts = 0
            existing.max_attempts = max_attempts
            existing.payload = payload or {}
            existing.locked_at = None
            existing.locked_by = None
            existing.started_at = None
            existing.finished_at = None
            existing.last_error = None
            existing.updated_at = now
        job_id = existing.id if existing is not None else None
    if job_id is None:
        raise RuntimeError(f"could not enqueue or find job {dedupe_key}")
    return int(job_id)


async def reprioritize_repository_jobs(session: AsyncSession) -> int:
    """Keep queued hydration ordered by the latest discovery evidence in one SQL update."""
    result = await session.execute(
        update(IngestionJob)
        .where(
            IngestionJob.status == "queued",
            IngestionJob.job_type.in_(["hydrate_repository", "refresh_repository"]),
            IngestionJob.candidate_id == RepositoryCandidate.id,
            RepositoryCandidate.tier.in_(["active", "pinned"]),
        )
        .values(
            priority=case(
                (RepositoryCandidate.tier == "pinned", 100),
                else_=25
                + cast(
                    func.least(70, func.round(RepositoryCandidate.trend_score)),
                    Integer,
                ),
            )
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)


class CollectorScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def tick(self, session: AsyncSession) -> dict[str, int]:
        now = datetime.now(UTC)
        lease_cutoff = now - timedelta(minutes=self.settings.collector_lease_minutes)
        recovery_result = await session.execute(
            update(IngestionJob)
            .where(
                IngestionJob.status == "running",
                IngestionJob.locked_at < lease_cutoff,
            )
            .values(
                status="queued",
                locked_at=None,
                locked_by=None,
                scheduled_for=now,
                updated_at=now,
                last_error="worker lease expired; safely re-queued",
            )
        )
        recovered = int(getattr(recovery_result, "rowcount", 0) or 0)
        collection = await ensure_default_collection(session, self.settings)
        await backfill_existing_repositories(session, self.settings, collection)
        discovery = 0
        day_key = now.strftime("%Y-%m-%d")
        for language in self.settings.discovery_language_list:
            await enqueue_job(
                session,
                "discover_github",
                f"discover:github:{language.casefold()}:{day_key}",
                payload={"language": language},
                collection_id=collection.id,
                priority=100,
                max_attempts=3,
            )
            discovery += 1
        if self.settings.gh_archive_enabled:
            latest = (now - timedelta(hours=self.settings.gh_archive_lag_hours)).replace(
                minute=0, second=0, microsecond=0
            )
            for offset in range(self.settings.gh_archive_hours_back):
                archive_hour = latest - timedelta(hours=offset)
                await enqueue_job(
                    session,
                    "discover_gharchive",
                    (
                        f"discover:gharchive:v{self.settings.gh_archive_algorithm_version}:"
                        f"{archive_hour:%Y-%m-%d-%H}"
                    ),
                    payload={
                        "archive_hour": archive_hour.isoformat(),
                        "algorithm_version": self.settings.gh_archive_algorithm_version,
                    },
                    collection_id=collection.id,
                    priority=90,
                    max_attempts=5,
                )
                discovery += 1
        reconcile_bucket = now.replace(minute=0, second=0, microsecond=0)
        await enqueue_job(
            session,
            "reconcile_collection",
            f"reconcile:{collection.id}:{reconcile_bucket.isoformat()}",
            collection_id=collection.id,
            priority=50,
            max_attempts=3,
        )
        due_candidates = (
            await session.scalars(
                select(RepositoryCandidate)
                .where(
                    RepositoryCandidate.eligible.is_(True),
                    RepositoryCandidate.classification.in_(SOFTWARE_CLASSIFICATIONS),
                    RepositoryCandidate.tier.in_(["active", "pinned"]),
                    (RepositoryCandidate.next_refresh_at.is_(None))
                    | (RepositoryCandidate.next_refresh_at <= now),
                )
                .order_by(RepositoryCandidate.tier.desc(), RepositoryCandidate.trend_score.desc())
                .limit(self.settings.collector_active_limit * 2)
            )
        ).all()
        refresh = 0
        refresh_bucket = now.strftime("%Y-%m-%d")
        for candidate in due_candidates:
            job_type = "refresh_repository" if candidate.repository_id else "hydrate_repository"
            await enqueue_job(
                session,
                job_type,
                f"{job_type}:{candidate.id}:{refresh_bucket}",
                candidate_id=candidate.id,
                repository_id=candidate.repository_id,
                priority=(
                    100
                    if candidate.tier == "pinned"
                    else 25 + min(70, round(candidate.trend_score))
                ),
                max_attempts=5,
            )
            refresh += 1
        await enqueue_job(
            session,
            "reconcile_directory",
            f"reconcile_directory:{day_key}",
            priority=85,
            max_attempts=3,
        )
        await enqueue_job(
            session,
            "scout_eval_batch",
            f"scout_eval_batch:{day_key}",
            priority=80,
            max_attempts=3,
        )
        await enqueue_job(
            session,
            "generate_embeddings",
            f"generate_embeddings:{day_key}",
            priority=70,
            max_attempts=3,
        )
        for language in self.settings.discovery_language_list[:2]:
            for s_min, s_max in [(0, 10), (11, 50), (51, 200)]:
                await enqueue_job(
                    session,
                    "discover_sharded",
                    f"discover:sharded:{language.casefold()}:{s_min}_{s_max}:{day_key}",
                    payload={"language": language, "star_min": s_min, "star_max": s_max},
                    priority=60,
                    max_attempts=3,
                )
        await enqueue_job(
            session,
            "maintenance",
            f"maintenance:{day_key}",
            priority=-10,
            max_attempts=2,
        )
        if self.settings.evidence_enabled:
            cohort = (
                await session.scalars(
                    select(CatalogRepository.github_id)
                    .where(CatalogRepository.is_deep.is_(True))
                    .order_by(CatalogRepository.last_observed_at.desc())
                    .limit(self.settings.evidence_cohort_limit)
                )
            ).all()
            for github_id in cohort:
                await enqueue_job(
                    session,
                    "collect_evidence",
                    f"evidence:{github_id}:{day_key}",
                    payload={"github_id": github_id},
                    priority=20,
                    max_attempts=3,
                )
        await session.commit()
        summary = {"discovery": discovery, "refresh": refresh, "recovered": recovered}
        log.info("collector_schedule_tick", **summary)
        return summary


class CollectorWorker:
    def __init__(
        self,
        github: GitHubClient,
        archive: GhArchiveClient,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.github = github
        self.archive = archive
        self.settings = settings or get_settings()
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"

    async def run_once(self) -> bool:
        async with SessionLocal() as session:
            job = await self._claim(session)
        if job is None:
            return False
        try:
            await self._execute(job.id)
        except GitHubRateLimitError as exc:
            await self._reschedule_rate_limited(job.id, exc)
        except Exception as exc:
            log.exception("collector_job_failed", job_id=job.id, job_type=job.job_type)
            await self._fail_or_retry(job.id, exc)
        else:
            await self._complete(job.id)
        return True

    async def _claim(self, session: AsyncSession) -> IngestionJob | None:
        now = datetime.now(UTC)
        job = await session.scalar(
            select(IngestionJob)
            .where(IngestionJob.status == "queued", IngestionJob.scheduled_for <= now)
            .order_by(IngestionJob.priority.desc(), IngestionJob.scheduled_for, IngestionJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status = "running"
        job.locked_at = now
        job.locked_by = self.worker_id
        job.started_at = job.started_at or now
        job.attempts += 1
        try:
            await session.commit()
            return job
        except Exception as exc:
            await session.rollback()
            log.error("collector_claim_commit_failed", job_id=job.id, error=str(exc))
            return None

    async def _execute(self, job_id: int) -> None:
        async with SessionLocal() as session:
            job = await session.get(IngestionJob, job_id)
            if job is None:
                return
            if job.job_type == "discover_github":
                await discover_github_repositories(
                    session, self.github, self.settings, str(job.payload["language"])
                )
            elif job.job_type == "discover_gharchive":
                archive_hour = datetime.fromisoformat(str(job.payload["archive_hour"]))
                existing = await session.get(GhArchiveFile, archive_hour)
                if (
                    not existing
                    or existing.status != "completed"
                    or existing.algorithm_version != self.settings.gh_archive_algorithm_version
                ):
                    result = await self.archive.read_hour(archive_hour)
                    await persist_gh_archive_hour(session, self.settings, archive_hour, result)
                    reconcile_bucket = datetime.now(UTC).strftime("%Y-%m-%d-%H")
                    await enqueue_job(
                        session,
                        "reconcile_collection",
                        (
                            "reconcile:archive:"
                            f"v{self.settings.gh_archive_algorithm_version}:{reconcile_bucket}"
                        ),
                        collection_id=job.collection_id,
                        priority=50,
                        max_attempts=3,
                    )
                    await session.commit()
            elif job.job_type == "reconcile_collection":
                newly_active, _, probe_ids = await reconcile_collection(session, self.settings)
                bucket = datetime.now(UTC).strftime("%Y-%m-%d")
                for candidate_id in newly_active:
                    await enqueue_job(
                        session,
                        "hydrate_repository",
                        f"hydrate_repository:{candidate_id}:{bucket}",
                        candidate_id=candidate_id,
                        priority=25,
                    )
                probe_bucket = datetime.now(UTC).strftime("%Y-%m-%d-%H")
                for candidate_id in probe_ids:
                    await enqueue_job(
                        session,
                        "probe_repository",
                        f"probe_repository:{candidate_id}:{probe_bucket}",
                        candidate_id=candidate_id,
                        priority=45,
                        max_attempts=3,
                    )
                await reprioritize_repository_jobs(session)
                await session.commit()
            elif job.job_type == "probe_repository":
                if job.candidate_id is None:
                    raise ValueError("probe job has no candidate")
                await probe_repository_candidate(session, self.github, job.candidate_id)
                reconcile_bucket = datetime.now(UTC).strftime("%Y-%m-%d-%H")
                await enqueue_job(
                    session,
                    "reconcile_collection",
                    f"reconcile:probe:{reconcile_bucket}",
                    collection_id=job.collection_id,
                    priority=40,
                    max_attempts=3,
                )
                await session.commit()
            elif job.job_type in {"hydrate_repository", "refresh_repository"}:
                await self._hydrate_candidate(session, job)
            elif job.job_type == "ingest_repository":
                full_name = str(job.payload["full_name"])
                try:
                    repo = await RepositoryIngester(session, self.github, self.settings).ingest(
                        full_name
                    )
                    await calculate_metrics(session, repo, 30)
                    await sync_catalog_from_repository(session, repo)
                except GitHubAPIError as err:
                    if err.status_code == 404:
                        log.warning("ingest_repository_not_found", repository=full_name)
                        return
                    raise
            elif job.job_type == "reconcile_directory":
                await reconcile_directory_and_cohort(session, self.settings)
            elif job.job_type == "scout_eval_batch":
                await run_daily_scout_batch(
                    session, limit=self.settings.scout_daily_eval_limit, settings=self.settings
                )
            elif job.job_type == "generate_embeddings":
                await generate_catalog_embeddings(session, limit=100, settings=self.settings)
            elif job.job_type == "discover_sharded":
                lang = str(job.payload["language"])
                s_min = int(job.payload.get("star_min", 0))
                s_max = int(job.payload.get("star_max", 10))
                await discover_github_sharded(
                    session,
                    self.github,
                    self.settings,
                    language=lang,
                    star_min=s_min,
                    star_max=s_max,
                )
            elif job.job_type == "maintenance":
                await self._maintenance(session)
            elif job.job_type == "collect_evidence":
                if self.settings.evidence_enabled:
                    await collect_repository_evidence(
                        session,
                        int(job.payload["github_id"]),
                        self.github,
                        self.settings,
                    )
            else:
                raise ValueError(f"unknown collector job type: {job.job_type}")
            await self._save_rate_state(session)

    async def _hydrate_candidate(self, session: AsyncSession, job: IngestionJob) -> None:
        if job.candidate_id is None:
            raise ValueError("repository job has no candidate")
        candidate = await session.get(RepositoryCandidate, job.candidate_id)
        if candidate is None:
            raise ValueError("candidate no longer exists")
        if not candidate.eligible or candidate.classification not in SOFTWARE_CLASSIFICATIONS:
            if candidate.tier != "pinned":
                candidate.tier = "candidate"
            await session.commit()
            log.info(
                "repository_hydration_skipped",
                repository=candidate.full_name,
                classification=candidate.classification,
                eligible=candidate.eligible,
            )
            return
        try:
            repo = await RepositoryIngester(session, self.github, self.settings).ingest(
                candidate.full_name, mode="refresh" if candidate.repository_id else "full"
            )
        except GitHubAPIError as err:
            if err.status_code == 404:
                candidate.eligible = False
                if candidate.tier != "pinned":
                    candidate.tier = "candidate"
                candidate.rejection_reason = "repository removed or private on github (404)"
                await session.commit()
                log.info(
                    "repository_hydration_not_found",
                    repository=candidate.full_name,
                    error=str(err),
                )
                return
            raise
        await calculate_metrics(session, repo, 30)
        await sync_catalog_from_repository(session, repo)
        candidate = await session.get(RepositoryCandidate, job.candidate_id)
        if candidate:
            candidate.repository_id = repo.id
            candidate.next_refresh_at = datetime.now(UTC) + timedelta(
                hours=self.settings.collector_active_refresh_hours
            )
            await session.commit()

    async def _maintenance(self, session: AsyncSession) -> None:
        await prune_evidence(session, self.settings)
        external_cutoff = datetime.now(UTC) - timedelta(
            days=self.settings.gh_archive_retention_days
        )
        activity_result = await session.execute(
            delete(ExternalRepositoryActivity).where(
                ExternalRepositoryActivity.period_start < external_cutoff
            )
        )
        files_result = await session.execute(
            delete(GhArchiveFile).where(GhArchiveFile.archive_hour < external_cutoff)
        )
        activity_deleted = int(getattr(activity_result, "rowcount", 0) or 0)
        files_deleted = int(getattr(files_result, "rowcount", 0) or 0)
        await session.commit()
        log.info(
            "collector_maintenance_completed",
            external_activity_deleted=activity_deleted,
            archive_files_deleted=files_deleted,
        )

    async def _save_rate_state(self, session: AsyncSession) -> None:
        if self.github.rate.limit is None:
            return
        now = datetime.now(UTC)
        value = {
            "limit": self.github.rate.limit,
            "remaining": self.github.rate.remaining,
            "used": self.github.rate.used,
            "reset_at": self.github.rate.reset_at.isoformat()
            if self.github.rate.reset_at
            else None,
            "resource": self.github.rate.resource,
            "process_requests": self.github.rate.request_count,
        }
        statement = insert(CollectorState).values(key="github_rate", value=value, updated_at=now)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[CollectorState.key],
                set_={
                    "value": statement.excluded.value,
                    "updated_at": statement.excluded.updated_at,
                },
            )
        )
        await session.commit()

    async def _complete(self, job_id: int) -> None:
        now = datetime.now(UTC)
        async with SessionLocal() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="completed",
                    locked_at=None,
                    locked_by=None,
                    finished_at=now,
                    updated_at=now,
                    last_error=None,
                )
            )
            await session.commit()

    async def _reschedule_rate_limited(self, job_id: int, error: GitHubRateLimitError) -> None:
        now = datetime.now(UTC)
        scheduled_for = max(error.reset_at or now + timedelta(hours=1), now) + timedelta(seconds=30)
        async with SessionLocal() as session:
            await session.execute(
                update(IngestionJob)
                .where(IngestionJob.id == job_id)
                .values(
                    status="queued",
                    locked_at=None,
                    locked_by=None,
                    scheduled_for=scheduled_for,
                    updated_at=now,
                    last_error=str(error),
                )
            )
            await self._save_rate_state(session)
        log.warning(
            "collector_rate_limited",
            job_id=job_id,
            resume_at=scheduled_for.isoformat(),
        )

    async def _fail_or_retry(self, job_id: int, error: Exception) -> None:
        now = datetime.now(UTC)
        async with SessionLocal() as session:
            job = await session.get(IngestionJob, job_id)
            if job is None:
                return
            is_404 = "404" in str(error)
            retry = (job.attempts < job.max_attempts) and not is_404
            job.status = "queued" if retry else ("cancelled" if is_404 else "failed")
            job.scheduled_for = now + timedelta(minutes=min(2**job.attempts, 360))
            job.locked_at = None
            job.locked_by = None
            job.finished_at = None if retry else now
            job.updated_at = now
            job.last_error = str(error)[:4000]
            await session.commit()


async def collect_forever(settings: Settings | None = None, once: bool = False) -> None:
    config = settings or get_settings()
    if not config.collector_enabled:
        log.warning("collector_disabled")
        if once:
            return
        await asyncio.Event().wait()
        return
    scheduler = CollectorScheduler(config)
    async with (
        GitHubClient(
            config.github_token,
            config.github_api_url,
            request_interval_seconds=config.github_request_interval_seconds,
            rate_limit_reserve=config.github_rate_limit_reserve,
        ) as github,
        GhArchiveClient(
            config.gh_archive_base_url, config.gh_archive_top_repositories_per_hour
        ) as archive,
    ):
        worker = CollectorWorker(github, archive, config)
        last_schedule = datetime.min.replace(tzinfo=UTC)
        while True:
            now = datetime.now(UTC)
            if now - last_schedule >= timedelta(minutes=1):
                async with SessionLocal() as session:
                    await scheduler.tick(session)
                last_schedule = now
            processed = await worker.run_once()
            if once:
                return
            if not processed:
                await asyncio.sleep(config.collector_poll_seconds)


async def collector_overview(session: AsyncSession) -> dict[str, Any]:
    tier_rows = (
        await session.execute(
            select(RepositoryCandidate.tier, func.count())
            .group_by(RepositoryCandidate.tier)
            .order_by(RepositoryCandidate.tier)
        )
    ).all()
    classification_rows = (
        await session.execute(
            select(RepositoryCandidate.classification, func.count())
            .group_by(RepositoryCandidate.classification)
            .order_by(RepositoryCandidate.classification)
        )
    ).all()
    job_rows = (
        await session.execute(
            select(IngestionJob.status, func.count())
            .group_by(IngestionJob.status)
            .order_by(IngestionJob.status)
        )
    ).all()
    rate = await session.get(CollectorState, "github_rate")
    last_archive = await session.scalar(select(func.max(GhArchiveFile.archive_hour)))
    archive_hours = await session.scalar(select(func.count()).select_from(GhArchiveFile))
    archive_events = await session.scalar(select(func.sum(GhArchiveFile.event_count)))
    archive_bytes = await session.scalar(select(func.sum(GhArchiveFile.compressed_bytes)))
    activity_rows = await session.scalar(
        select(func.count()).select_from(ExternalRepositoryActivity)
    )
    hydrated = await session.scalar(
        select(func.count())
        .select_from(RepositoryCandidate)
        .where(RepositoryCandidate.repository_id.is_not(None))
    )
    oldest_queued = await session.scalar(
        select(func.min(IngestionJob.created_at)).where(IngestionJob.status == "queued")
    )
    last_completed = await session.scalar(
        select(func.max(IngestionJob.finished_at)).where(IngestionJob.status == "completed")
    )
    try:
        database_size = await session.scalar(select(func.pg_database_size(func.current_database())))
    except Exception:
        # Keep the status endpoint usable with restricted/read-only database roles.
        await session.rollback()
        database_size = None
    catalog_total = await session.scalar(select(func.count()).select_from(CatalogRepository))
    directory_total = await session.scalar(
        select(func.count()).where(CatalogRepository.is_directory.is_(True))
    )
    deep_total = await session.scalar(
        select(func.count()).where(CatalogRepository.is_deep.is_(True))
    )
    scout_total = await session.scalar(
        select(func.count()).where(ScoutAssessment.is_current.is_(True))
    )
    embeddings_total = await session.scalar(select(func.count()).select_from(RepositoryEmbedding))

    return {
        "tiers": {name: int(count) for name, count in tier_rows},
        "classifications": {name: int(count) for name, count in classification_rows},
        "jobs": {name: int(count) for name, count in job_rows},
        "github_rate": rate.value if rate else {},
        "last_archive_hour": last_archive,
        "archive_hours_processed": int(archive_hours or 0),
        "archive_events_processed": int(archive_events or 0),
        "archive_compressed_bytes": int(archive_bytes or 0),
        "external_activity_rows": int(activity_rows or 0),
        "hydrated_repositories": int(hydrated or 0),
        "catalog_repositories": int(catalog_total or 0),
        "directory_members": int(directory_total or 0),
        "deep_cohort_members": int(deep_total or 0),
        "scout_assessments": int(scout_total or 0),
        "repository_embeddings": int(embeddings_total or 0),
        "database_size_bytes": int(database_size) if database_size is not None else None,
        "oldest_queued_at": oldest_queued,
        "last_completed_at": last_completed,
    }
