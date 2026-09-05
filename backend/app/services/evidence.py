"""Collect once for the cohort, reuse everywhere. Public reads never trigger network work."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    CatalogRepository,
    ExternalEvidenceItem,
    Issue,
    Release,
    RepositoryChangeEvent,
    RepositoryExternalLink,
    RepositorySearchDocument,
    RepositorySourceSnapshot,
    RepositorySourceState,
)
from app.github.client import GitHubAPIError, GitHubClient
from app.services.evidence_sources import (
    PACKAGE_ADAPTERS,
    DepsDevAdapter,
    Evidence,
    HackerNewsAdapter,
    NpmDownloadsAdapter,
    Observation,
    OsvAdapter,
    PypiDownloadsAdapter,
    SourceAdapter,
    SourceHTTP,
    SourceUnavailable,
    github_name,
    package_targets,
)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def fingerprint(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def changes_between(
    source: str,
    previous: dict[str, Any],
    current: dict[str, Any],
    cfg: Settings,
) -> list[tuple[str, str]]:
    if not previous:
        return []  # First observation is a baseline, not a change.
    changes = []
    if source == "github":
        if previous.get("license") and current.get("license"):
            if previous["license"] != current["license"]:
                changes.append(
                    (
                        "LICENSE_CHANGED",
                        f"License changed: {previous['license']} → {current['license']}",
                    )
                )
        if previous.get("dormant") is False and current.get("dormant") is True:
            changes.append(
                ("PROJECT_BECAME_DORMANT", "No recorded push within the dormancy window")
            )
        if previous.get("dormant") is True and current.get("dormant") is False:
            changes.append(("PROJECT_RESUMED", "Repository push activity resumed"))
    before, after = previous.get("downloads"), current.get("downloads")
    if isinstance(before, int) and isinstance(after, int) and before > 0:
        delta = after - before
        if abs(delta) >= cfg.evidence_adoption_min_delta:
            if abs(delta) / before >= cfg.evidence_adoption_change_ratio:
                kind = "INCREASED" if delta > 0 else "DECREASED"
                changes.append(
                    (
                        f"PACKAGE_ADOPTION_{kind}",
                        f"Weekly package downloads: {before:,} → {after:,} (not users)",
                    )
                )
    return changes


async def save_observation(
    session: AsyncSession,
    repo: CatalogRepository,
    source: str,
    external_id: str,
    observation: Observation,
    refresh_hours: int,
    cfg: Settings,
) -> None:
    now = datetime.now(UTC)
    key = (repo.github_id, source, external_id)
    state = await session.get(RepositorySourceState, key)
    previous = state.facts if state else {}
    if state is None:
        state = RepositorySourceState(
            github_id=repo.github_id,
            source=source,
            external_id=external_id,
            facts={},
        )
        session.add(state)
    state.last_success_at = now
    state.last_attempt_at = now
    state.next_refresh_at = now + timedelta(hours=refresh_hours)
    state.last_error = None
    state.facts = observation.facts
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    snapshot = insert(RepositorySourceSnapshot).values(
        github_id=repo.github_id,
        source=source,
        external_id=external_id,
        captured_at=day,
        facts=observation.facts,
    )
    await session.execute(
        snapshot.on_conflict_do_update(
            constraint="uq_source_snapshot_day",
            set_={"facts": observation.facts},
        )
        if session.bind is not None and session.bind.dialect.name == "postgresql"
        else snapshot.on_conflict_do_update(
            index_elements=["github_id", "source", "external_id", "captured_at"],
            set_={"facts": observation.facts},
        )
    )
    for item in observation.items[:40]:
        fp = fingerprint(
            source,
            item.details.get("target_url")
            if source == "hacker_news" and item.kind == "announcement"
            else item.external_id,
        )
        existing = await session.scalar(
            select(ExternalEvidenceItem).where(
                ExternalEvidenceItem.github_id == repo.github_id,
                ExternalEvidenceItem.fingerprint == fp,
            )
        )
        is_new = existing is None
        if existing is None:
            existing = ExternalEvidenceItem(github_id=repo.github_id, source=source, fingerprint=fp)
            session.add(existing)
        for field, value in item.model_dump().items():
            setattr(existing, field, value)
        existing.observed_at = now
        await session.flush()
        event_kind = {
            "release": "RELEASE_PUBLISHED",
            "vulnerability": "VULNERABILITY_DISCOVERED",
            "discussion": "NEW_RELEVANT_DISCUSSION",
            "announcement": "NEW_RELEVANT_DISCUSSION",
        }.get(item.kind)
        if is_new and event_kind:
            await save_change(
                session,
                repo.github_id,
                event_kind,
                item.title,
                item.url,
                utc(item.published_at)
                if item.published_at and item.kind != "vulnerability"
                else now,
                fingerprint(event_kind, fp),
                existing.id,
            )
    for kind, title in changes_between(source, previous, observation.facts, cfg):
        url = str(observation.facts.get("url") or f"https://github.com/{repo.full_name}")
        await save_change(
            session,
            repo.github_id,
            kind,
            title,
            url,
            now,
            fingerprint(source, external_id, kind, day, observation.facts),
        )
    await session.flush()


async def save_change(
    session: AsyncSession,
    github_id: int,
    kind: str,
    title: str,
    url: str,
    occurred_at: datetime,
    fp: str,
    evidence_id: int | None = None,
) -> None:
    stmt = (
        insert(RepositoryChangeEvent)
        .values(
            github_id=github_id,
            kind=kind,
            title=title[:300],
            source_url=url[:2048],
            occurred_at=occurred_at,
            observed_at=datetime.now(UTC),
            fingerprint=fp,
            evidence_id=evidence_id,
        )
        .on_conflict_do_nothing(index_elements=["github_id", "fingerprint"])
    )
    await session.execute(stmt)


async def record_failure(
    session: AsyncSession,
    gid: int,
    source: str,
    external_id: str,
    error: SourceUnavailable,
) -> None:
    now = datetime.now(UTC)
    state = await session.get(RepositorySourceState, (gid, source, external_id))
    if state is None:
        state = RepositorySourceState(
            github_id=gid, source=source, external_id=external_id, facts={}
        )
        session.add(state)
    state.last_attempt_at = now
    state.next_refresh_at = now + timedelta(seconds=max(3600, error.retry_seconds))
    state.last_error = str(error)[:500]
    await session.flush()


async def due(session: AsyncSession, gid: int, source: str, external_id: str) -> bool:
    state = await session.get(RepositorySourceState, (gid, source, external_id))
    return state is None or utc(state.next_refresh_at) <= datetime.now(UTC)


async def verified_package(
    github: GitHubClient,
    gid: int,
    urls: list[str],
) -> str | None:
    names = {name for url in urls if (name := github_name(url))}
    if len(names) != 1:
        return None  # Conflicting project links are ambiguous, even if one matches.
    name = next(iter(names))
    payload = await github.get_json(f"/repos/{name}")
    return f"https://github.com/{payload['full_name']}" if payload.get("id") == gid else None


async def collect_github(
    session: AsyncSession,
    repo: CatalogRepository,
    github: GitHubClient,
    cfg: Settings,
) -> str:
    doc = await session.get(RepositorySearchDocument, repo.github_id)
    readme = doc.readme_text if doc else ""
    if await due(session, repo.github_id, "github_readme", repo.full_name):
        try:
            payload = await github.get_json(f"/repos/{repo.full_name}/readme")
            if payload.get("size", 0) > 100_000:
                raise SourceUnavailable("README exceeds collection size bound")
            readme = base64.b64decode(payload.get("content", "")).decode("utf-8", errors="replace")[
                :20000
            ]
            if doc:
                doc.readme_text = readme
            repo.readme_excerpt = readme[:1200] or None
            await save_observation(
                session,
                repo,
                "github_readme",
                repo.full_name,
                Observation(facts={"url": f"https://github.com/{repo.full_name}#readme"}),
                168,
                cfg,
            )
        except (GitHubAPIError, ValueError, SourceUnavailable):
            await record_failure(
                session,
                repo.github_id,
                "github_readme",
                repo.full_name,
                SourceUnavailable("README unavailable", 86400),
            )
    items = []
    if repo.repository_id:
        releases = (
            await session.scalars(
                select(Release)
                .where(
                    Release.repository_id == repo.repository_id,
                    Release.draft.is_(False),
                )
                .order_by(Release.published_at.desc())
                .limit(20)
            )
        ).all()
        for release in releases:
            items.append(
                Evidence(
                    external_id=str(release.github_id),
                    kind="release",
                    title=release.tag[:300],
                    url=(
                        f"https://github.com/{repo.full_name}/releases/tag/"
                        + quote(release.tag, safe="")
                    ),
                    published_at=release.published_at,
                    details={"prerelease": release.prerelease},
                )
            )
        issues = (
            await session.scalars(
                select(Issue)
                .where(
                    Issue.repository_id == repo.repository_id,
                    Issue.state == "open",
                )
                .order_by(Issue.comments.desc(), Issue.updated_at.desc())
                .limit(5)
            )
        ).all()
        for issue in issues:
            items.append(
                Evidence(
                    external_id=f"issue:{issue.number}",
                    kind="issue",
                    title=f"Open issue #{issue.number}",
                    author=issue.author_login,
                    url=f"https://github.com/{repo.full_name}/issues/{issue.number}",
                    published_at=issue.created_at,
                    details={
                        "labels": [label.get("name") for label in issue.labels][:10],
                        "comments": issue.comments,
                        "selection": "most discussed sampled open issues",
                    },
                )
            )
    dormant = (
        (datetime.now(UTC) - utc(repo.pushed_at)).days >= cfg.evidence_dormant_days
        if repo.pushed_at
        else None
    )
    await save_observation(
        session,
        repo,
        "github",
        repo.full_name,
        Observation(
            facts={
                "license": repo.license,
                "dormant": dormant,
                "url": f"https://github.com/{repo.full_name}",
                "stars": repo.stars,
                "metadata_observed_at": repo.last_observed_at.isoformat(),
            },
            items=items,
        ),
        cfg.evidence_refresh_hours,
        cfg,
    )
    return readme


async def collect_repository_evidence(
    session: AsyncSession,
    github_id: int,
    github: GitHubClient,
    cfg: Settings,
) -> None:
    # Serialize same-repository work, including lease replay; writes are also deduplicated.
    repo = await session.scalar(
        select(CatalogRepository)
        .where(
            CatalogRepository.github_id == github_id,
        )
        .with_for_update()
    )
    if repo is None:
        return
    readme = await collect_github(session, repo, github, cfg)
    async with httpx.AsyncClient() as http:
        client = SourceHTTP(http)

        async def run(adapter: SourceAdapter, key: str) -> None:
            if not await due(session, github_id, adapter.source, key):
                return
            try:
                result = await adapter.collect(client, key)
                await save_observation(
                    session, repo, adapter.source, key, result, adapter.refresh_hours, cfg
                )
            except (SourceUnavailable, ValueError, KeyError, TypeError) as exc:
                error = (
                    exc
                    if isinstance(exc, SourceUnavailable)
                    else SourceUnavailable("Source response could not be normalized")
                )
                await record_failure(session, github_id, adapter.source, key, error)

        links = (
            await session.scalars(
                select(RepositoryExternalLink)
                .where(
                    RepositoryExternalLink.github_id == github_id,
                )
                .limit(4)
            )
        ).all()
        targets = sorted(
            set(package_targets(readme)) | {(link.source, link.external_id) for link in links}
        )[:4]
        for source, package in targets:
            adapter = PACKAGE_ADAPTERS.get(source)
            if adapter is None:
                continue
            if await due(session, github_id, source, package):
                try:
                    result = await adapter.collect(client, package)
                    matched = await verified_package(github, github_id, result.repository_urls)
                    if matched is None:
                        raise SourceUnavailable(
                            "Package linkage unresolved: repository identity mismatch", 604800
                        )
                    stmt = insert(RepositoryExternalLink).values(
                        github_id=github_id,
                        source=source,
                        external_id=package,
                        canonical_url=result.items[0].url,
                        match_method="package_repository_github_id",
                        match_confidence=1.0,
                        verification="verified",
                        provenance_url=matched,
                        observed_at=datetime.now(UTC),
                    )
                    await session.execute(
                        stmt.on_conflict_do_update(
                            index_elements=["github_id", "source", "external_id"],
                            set_={"observed_at": datetime.now(UTC), "verification": "verified"},
                        )
                    )
                    await save_observation(
                        session, repo, source, package, result, adapter.refresh_hours, cfg
                    )
                except (SourceUnavailable, GitHubAPIError, ValueError, KeyError, TypeError) as exc:
                    await record_failure(
                        session,
                        github_id,
                        source,
                        package,
                        SourceUnavailable(
                            str(exc)
                            if isinstance(exc, SourceUnavailable)
                            else "Package verification unavailable",
                            604800,
                        ),
                    )
            state = await session.get(RepositorySourceState, (github_id, source, package))
            if state is None or state.last_error or not state.facts.get("version"):
                continue
            ecosystem = "npm" if source == "npm" else "PyPI"
            key = f"{ecosystem}:{package}:{state.facts['version']}"
            await run(NpmDownloadsAdapter() if source == "npm" else PypiDownloadsAdapter(), package)
            await run(DepsDevAdapter(), key)
            await run(OsvAdapter(), key)
        await run(HackerNewsAdapter(), repo.full_name)
    await prune_evidence(session, cfg, github_id)
    await session.commit()


async def prune_evidence(session: AsyncSession, cfg: Settings, gid: int | None = None) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=cfg.evidence_retention_days)
    for model, column in (
        (RepositoryChangeEvent, RepositoryChangeEvent.observed_at),
        (ExternalEvidenceItem, ExternalEvidenceItem.observed_at),
        (RepositorySourceSnapshot, RepositorySourceSnapshot.captured_at),
    ):
        await session.execute(delete(model).where(column < cutoff))
    if gid is not None:
        for model, date in (
            (ExternalEvidenceItem, ExternalEvidenceItem.observed_at),
            (RepositoryChangeEvent, RepositoryChangeEvent.observed_at),
        ):
            keep = (
                select(model.id)
                .where(model.github_id == gid)
                .order_by(
                    date.desc(),
                    model.id.desc(),
                )
                .limit(cfg.evidence_items_per_repository)
            )
            await session.execute(
                delete(model).where(model.github_id == gid, model.id.not_in(keep))
            )
