import math
import re
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import orjson
import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import (
    Collection,
    CollectionMembership,
    ExternalRepositoryActivity,
    GhArchiveFile,
    IngestionJob,
    Repository,
    RepositoryCandidate,
)
from app.github.client import GitHubAPIError, GitHubClient

log = structlog.get_logger()


@dataclass(slots=True)
class ArchiveActivity:
    github_id: int
    full_name: str
    star_events: int = 0
    fork_events: int = 0
    push_events: int = 0
    pull_request_events: int = 0
    issue_events: int = 0
    release_events: int = 0

    @property
    def weighted_events(self) -> float:
        # Push volume is cheap to manufacture and routinely dominated the first collector
        # trial. It remains useful as a tie-breaker, but cannot outweigh genuine adoption or
        # collaboration signals.
        return (
            self.star_events * 10
            + self.fork_events * 6
            + min(self.push_events, 20) * 0.05
            + self.pull_request_events * 2
            + self.issue_events
            + self.release_events * 4
        )


@dataclass(slots=True)
class ArchiveResult:
    repositories: list[ArchiveActivity]
    event_count: int
    compressed_bytes: int


@dataclass(frozen=True, slots=True)
class RepositoryClassification:
    category: str
    confidence: float
    eligible: bool
    reason: str | None = None


SOFTWARE_CLASSIFICATIONS = {
    "library",
    "framework",
    "developer_tool",
    "software",
}

_RESOURCE_TOPICS = {
    "awesome",
    "awesome-list",
    "books",
    "cheatsheet",
    "coding-interview",
    "course",
    "curriculum",
    "education",
    "free-programming-books",
    "guide",
    "interview",
    "learning",
    "learning-resources",
    "list",
    "resources",
    "roadmap",
    "system-design",
    "style-guide",
    "tutorial",
    "tutorials",
}
_TEMPLATE_TOPICS = {
    "boilerplate",
    "cookiecutter",
    "hacktoberfest-template",
    "starter",
    "starter-kit",
    "template",
}
_LIBRARY_TOPICS = {
    "api-client",
    "component-library",
    "database-driver",
    "http-client",
    "library",
    "machine-learning-library",
    "npm-package",
    "orm",
    "package",
    "python-library",
    "react-library",
    "serialization",
    "testing-library",
}
_FRAMEWORK_TOPICS = {
    "css-framework",
    "deep-learning-framework",
    "framework",
    "frontend-framework",
    "machine-learning-framework",
    "react-framework",
    "web-framework",
}
_TOOL_TOPICS = {
    "build-tool",
    "cli",
    "command-line",
    "compiler",
    "container",
    "database",
    "developer-tools",
    "devops",
    "formatter",
    "kubernetes",
    "linter",
    "observability",
    "package-manager",
    "parser",
    "runtime",
    "sdk",
    "static-analysis",
    "testing",
}
_RESOURCE_NAMES = {
    "build-your-own-x",
    "developer-roadmap",
    "free-programming-books",
    "public-apis",
    "system-design-primer",
}


def _normalise_topics(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {str(topic).strip().casefold().replace("_", "-") for topic in value if str(topic).strip()}
    )


def classify_repository(item: dict[str, Any]) -> RepositoryClassification:
    """Classify cheap discovery metadata before spending the core API budget.

    This is intentionally a transparent eligibility gate, not an ML claim. Uncertain code
    repositories remain software candidates; only strong editorial/template signals are
    rejected automatically.
    """
    topics = set(_normalise_topics(item.get("topics")))
    name = str(item.get("name") or "").casefold().replace("_", "-")
    description = str(item.get("description") or "").casefold()
    description_tokens = set(re.findall(r"[a-z0-9]+", description))

    resource_match = sorted(topics & _RESOURCE_TOPICS)
    resource_description = any(
        phrase in description
        for phrase in (
            "awesome list",
            "curated list",
            "collection of resources",
            "free programming books",
            "learning roadmap",
            "interview questions",
            "style guide",
        )
    )
    if (
        resource_match
        or name in _RESOURCE_NAMES
        or name.startswith("awesome-")
        or resource_description
        or ({"roadmap", "learning"} & description_tokens and "resources" in description_tokens)
    ):
        signal = resource_match[0] if resource_match else name or "description"
        return RepositoryClassification(
            "learning_resource", 0.97, False, f"editorial/resource signal: {signal}"
        )

    template_match = sorted(topics & _TEMPLATE_TOPICS)
    if template_match or name.endswith("-boilerplate") or name.endswith("-starter"):
        signal = template_match[0] if template_match else name
        return RepositoryClassification("template", 0.93, False, f"template signal: {signal}")

    if topics & _LIBRARY_TOPICS:
        return RepositoryClassification("library", 0.94, True)
    if topics & _FRAMEWORK_TOPICS:
        return RepositoryClassification("framework", 0.94, True)
    if topics & _TOOL_TOPICS:
        return RepositoryClassification("developer_tool", 0.88, True)
    if item.get("language"):
        return RepositoryClassification("software", 0.62, True)
    return RepositoryClassification("unclassified", 0.2, True, "metadata probe required")


def apply_archive_event(aggregates: dict[int, ArchiveActivity], event: dict[str, Any]) -> bool:
    """Fold one public event into repository-level facts without retaining its payload."""
    repo = event.get("repo") or {}
    github_id = repo.get("id")
    full_name = repo.get("name")
    event_type = event.get("type")
    if not isinstance(github_id, int) or not isinstance(full_name, str) or "/" not in full_name:
        return False
    if event_type not in {
        "WatchEvent",
        "ForkEvent",
        "PushEvent",
        "PullRequestEvent",
        "IssuesEvent",
        "ReleaseEvent",
    }:
        return False
    payload = event.get("payload") or {}
    activity = aggregates.setdefault(github_id, ArchiveActivity(github_id, full_name))
    activity.full_name = full_name
    if event_type == "WatchEvent" and payload.get("action", "started") == "started":
        activity.star_events += 1
    elif event_type == "ForkEvent":
        activity.fork_events += 1
    elif event_type == "PushEvent":
        activity.push_events += 1
    elif event_type == "PullRequestEvent":
        activity.pull_request_events += 1
    elif event_type == "IssuesEvent":
        activity.issue_events += 1
    elif event_type == "ReleaseEvent":
        activity.release_events += 1
    return True


def aggregate_archive_events(events: Iterable[dict[str, Any]], limit: int) -> list[ArchiveActivity]:
    aggregates: dict[int, ArchiveActivity] = {}
    for event in events:
        apply_archive_event(aggregates, event)
    return select_archive_activities(aggregates.values(), limit)


def select_archive_activities(
    activities: Iterable[ArchiveActivity], limit: int
) -> list[ArchiveActivity]:
    """Keep a compact but diverse discovery sample from one archive hour.

    A union of adoption and collaboration leaders prevents high-frequency push streams from
    evicting repositories that are actually gaining users. The final fill remains deterministic
    and bounded, so database growth is `hours × limit`, independent of raw archive size.
    """
    if limit <= 0:
        return []
    items = list(activities)
    if len(items) <= limit:
        return sorted(items, key=lambda item: (-item.weighted_events, item.full_name.casefold()))

    star_quota = max(1, round(limit * 0.6))
    fork_quota = max(1, round(limit * 0.15))
    collaboration_quota = max(1, limit - star_quota - fork_quota)
    selected: dict[int, ArchiveActivity] = {}

    def take(ranked: list[ArchiveActivity], quota: int) -> None:
        for activity in ranked:
            if len(selected) >= limit or quota <= 0:
                break
            if activity.github_id not in selected:
                selected[activity.github_id] = activity
                quota -= 1

    take(
        sorted(
            (item for item in items if item.star_events),
            key=lambda item: (-item.star_events, -item.weighted_events, item.full_name.casefold()),
        ),
        star_quota,
    )
    take(
        sorted(
            (item for item in items if item.fork_events),
            key=lambda item: (-item.fork_events, -item.weighted_events, item.full_name.casefold()),
        ),
        fork_quota,
    )
    take(
        sorted(
            items,
            key=lambda item: (
                -(item.pull_request_events + item.issue_events + item.release_events * 2),
                -item.weighted_events,
                item.full_name.casefold(),
            ),
        ),
        collaboration_quota,
    )
    take(
        sorted(items, key=lambda item: (-item.weighted_events, item.full_name.casefold())),
        limit - len(selected),
    )
    return sorted(
        selected.values(), key=lambda item: (-item.weighted_events, item.full_name.casefold())
    )[:limit]


class GhArchiveClient:
    """Streaming GH Archive reader that stores aggregates, never multi-gigabyte raw events."""

    def __init__(self, base_url: str, top_repositories: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.top_repositories = top_repositories
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(180, connect=20), follow_redirects=True
        )

    async def __aenter__(self) -> "GhArchiveClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.client.aclose()

    async def read_hour(self, archive_hour: datetime) -> ArchiveResult:
        hour = archive_hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        url = f"{self.base_url}/{hour:%Y-%m-%d-%-H}.json.gz"
        aggregates: dict[int, ArchiveActivity] = {}
        event_count = 0
        compressed_bytes = 0
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        buffer = b""
        async with self.client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_raw():
                compressed_bytes += len(chunk)
                buffer += decompressor.decompress(chunk)
                lines = buffer.split(b"\n")
                buffer = lines.pop()
                for line in lines:
                    if not line:
                        continue
                    try:
                        event = orjson.loads(line)
                    except orjson.JSONDecodeError:
                        continue
                    event_count += 1
                    apply_archive_event(aggregates, event)
        buffer += decompressor.flush()
        if buffer.strip():
            try:
                event = orjson.loads(buffer)
                event_count += 1
                apply_archive_event(aggregates, event)
            except orjson.JSONDecodeError:
                pass
        repositories = select_archive_activities(aggregates.values(), self.top_repositories)
        return ArchiveResult(repositories, event_count, compressed_bytes)


async def ensure_default_collection(session: AsyncSession, settings: Settings) -> Collection:
    collection = await session.scalar(select(Collection).where(Collection.slug == "oss-libraries"))
    now = datetime.now(UTC)
    if collection is None:
        collection = Collection(
            slug="oss-libraries",
            name="Open-source software universe",
            description=(
                "Libraries, frameworks, and developer software discovered through GitHub Search "
                "and adoption signals in GH Archive public events."
            ),
            candidate_limit=settings.collector_candidate_limit,
            active_limit=settings.collector_active_limit,
            refresh_hours=settings.collector_active_refresh_hours,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        session.add(collection)
        await session.flush()
    elif collection.name == "OSS library universe":
        collection.name = "Open-source software universe"
        collection.description = (
            "Libraries, frameworks, and developer software discovered through GitHub Search "
            "and adoption signals in GH Archive public events."
        )
    return collection


async def backfill_existing_repositories(
    session: AsyncSession, settings: Settings, collection: Collection
) -> int:
    """Link repositories created before the collector tables existed as pinned candidates."""
    repositories = list(
        (
            await session.scalars(
                select(Repository)
                .outerjoin(
                    RepositoryCandidate,
                    RepositoryCandidate.github_id == Repository.github_id,
                )
                .where(RepositoryCandidate.id.is_(None))
            )
        ).all()
    )
    if not repositories:
        return 0
    now = datetime.now(UTC)
    values = []
    for repository in repositories:
        classification = classify_repository(
            {
                "name": repository.name,
                "description": repository.description,
                "language": repository.primary_language,
                "topics": [],
            }
        )
        values.append(
            {
                "github_id": repository.github_id,
                "repository_id": repository.id,
                "owner": repository.owner,
                "name": repository.name,
                "full_name": repository.full_name,
                "description": repository.description,
                "primary_language": repository.primary_language,
                "topics": [],
                "classification": classification.category,
                "classification_confidence": classification.confidence,
                "rejection_reason": classification.reason,
                "stars": repository.stars,
                "forks": repository.forks,
                "pushed_at": repository.pushed_at,
                "archived": repository.archived,
                "is_fork": False,
                "source": "existing_repository",
                "source_score": 0,
                "trend_score": 0,
                "trend_components": {"provisional": True},
                "tier": "pinned",
                "eligible": not repository.archived,
                "discovered_at": repository.last_ingested_at or now,
                "last_seen_at": now,
                "promoted_at": now,
                "next_refresh_at": now,
            }
        )
    statement = insert(RepositoryCandidate).values(values)
    await session.execute(
        statement.on_conflict_do_nothing(index_elements=[RepositoryCandidate.github_id])
    )
    await session.flush()
    candidate_ids = list(
        (
            await session.scalars(
                select(RepositoryCandidate.id).where(
                    RepositoryCandidate.repository_id.in_(
                        [repository.id for repository in repositories]
                    )
                )
            )
        ).all()
    )
    if candidate_ids:
        memberships = insert(CollectionMembership).values(
            [
                {
                    "collection_id": collection.id,
                    "candidate_id": candidate_id,
                    "source": "existing_repository",
                    "score": 0,
                    "selected": True,
                    "last_ranked_at": now,
                }
                for candidate_id in candidate_ids
            ]
        )
        await session.execute(
            memberships.on_conflict_do_nothing(
                index_elements=[
                    CollectionMembership.collection_id,
                    CollectionMembership.candidate_id,
                ]
            )
        )
    await session.flush()
    log.info("existing_repositories_linked", repositories=len(candidate_ids))
    return len(candidate_ids)


def github_candidate_values(item: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    owner = (item.get("owner") or {}).get("login")
    name = item.get("name")
    full_name = item.get("full_name")
    github_id = item.get("id")
    if not owner or not name or not full_name or not isinstance(github_id, int):
        return None
    pushed_at = item.get("pushed_at")
    stars = int(item.get("stargazers_count") or 0)
    topics = _normalise_topics(item.get("topics"))
    classification = classify_repository(item)
    structurally_eligible = not item.get("archived") and not item.get("fork")
    return {
        "github_id": github_id,
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "description": item.get("description"),
        "primary_language": item.get("language"),
        "topics": topics,
        "classification": classification.category,
        "classification_confidence": classification.confidence,
        "rejection_reason": classification.reason,
        "stars": stars,
        "forks": int(item.get("forks_count") or 0),
        "pushed_at": datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        if pushed_at
        else None,
        "archived": bool(item.get("archived")),
        "is_fork": bool(item.get("fork")),
        "source": "github_search",
        "source_score": round(math.log1p(stars), 4),
        "trend_score": 0.0,
        "trend_components": {},
        "tier": "candidate",
        "eligible": structurally_eligible and classification.eligible,
        "discovered_at": now,
        "last_seen_at": now,
        "next_refresh_at": now,
    }


async def probe_repository_candidate(
    session: AsyncSession,
    github: GitHubClient,
    candidate_id: int,
) -> RepositoryCandidate:
    """Resolve a GH Archive-only candidate with one inexpensive repository request."""
    candidate = await session.get(RepositoryCandidate, candidate_id)
    if candidate is None:
        raise ValueError("candidate no longer exists")
    try:
        payload = await github.get_json(f"/repos/{candidate.full_name}")
    except GitHubAPIError as exc:
        if "404" in str(exc):
            candidate.eligible = False
            candidate.rejection_reason = "repository not found on github (404)"
            candidate.last_seen_at = datetime.now(UTC)
            await session.commit()
            log.info("candidate_probe_not_found", repository=candidate.full_name)
            return candidate
        raise
    values = github_candidate_values(payload, datetime.now(UTC))
    if values is None:
        raise ValueError(f"GitHub returned incomplete metadata for {candidate.full_name}")
    for key in (
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
        "eligible",
        "last_seen_at",
    ):
        setattr(candidate, key, values[key])
    await session.commit()
    log.info(
        "candidate_probe_completed",
        repository=candidate.full_name,
        classification=candidate.classification,
        eligible=candidate.eligible,
    )
    return candidate


async def reclassify_stored_candidates(session: AsyncSession) -> dict[str, int]:
    """Reapply the transparent metadata gate after its rules change."""
    candidates = list((await session.scalars(select(RepositoryCandidate))).all())
    counts: dict[str, int] = {}
    for candidate in candidates:
        classification = classify_repository(
            {
                "name": candidate.name,
                "description": candidate.description,
                "language": candidate.primary_language,
                "topics": candidate.topics or [],
            }
        )
        candidate.classification = classification.category
        candidate.classification_confidence = classification.confidence
        candidate.rejection_reason = classification.reason
        if candidate.tier != "pinned":
            candidate.eligible = (
                not candidate.archived and not candidate.is_fork and classification.eligible
            )
        counts[classification.category] = counts.get(classification.category, 0) + 1
    await session.commit()
    log.info("candidate_reclassification_completed", candidates=len(candidates), classes=counts)
    return counts


async def discover_github_repositories(
    session: AsyncSession,
    github: GitHubClient,
    settings: Settings,
    language: str,
) -> int:
    now = datetime.now(UTC)
    pushed_after = (now - timedelta(days=settings.discovery_pushed_within_days)).date().isoformat()
    query = (
        f"is:public archived:false fork:false stars:>={settings.discovery_min_stars} "
        f"pushed:>={pushed_after} language:{language}"
    )
    items = await github.search_repositories(query, settings.discovery_results_per_language)
    values = [value for item in items if (value := github_candidate_values(item, now))]
    if not values:
        return 0
    statement = insert(RepositoryCandidate).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[RepositoryCandidate.github_id],
        set_={
            "owner": excluded.owner,
            "name": excluded.name,
            "full_name": excluded.full_name,
            "description": excluded.description,
            "primary_language": excluded.primary_language,
            "topics": excluded.topics,
            "classification": excluded.classification,
            "classification_confidence": excluded.classification_confidence,
            "rejection_reason": excluded.rejection_reason,
            "stars": excluded.stars,
            "forks": excluded.forks,
            "pushed_at": excluded.pushed_at,
            "archived": excluded.archived,
            "is_fork": excluded.is_fork,
            "source": excluded.source,
            "source_score": excluded.source_score,
            "eligible": excluded.eligible,
            "last_seen_at": excluded.last_seen_at,
        },
    )
    await session.execute(statement)
    await session.flush()
    collection = await ensure_default_collection(session, settings)
    ids = list(
        (
            await session.scalars(
                select(RepositoryCandidate.id).where(
                    RepositoryCandidate.github_id.in_([value["github_id"] for value in values])
                )
            )
        ).all()
    )
    membership = insert(CollectionMembership).values(
        [
            {
                "collection_id": collection.id,
                "candidate_id": candidate_id,
                "source": "github_search",
                "score": 0.0,
                "selected": False,
            }
            for candidate_id in ids
        ]
    )
    await session.execute(
        membership.on_conflict_do_update(
            index_elements=[
                CollectionMembership.collection_id,
                CollectionMembership.candidate_id,
            ],
            set_={"source": membership.excluded.source},
        )
    )
    await session.commit()
    log.info("github_discovery_completed", language=language, repositories=len(values))
    return len(values)


async def persist_gh_archive_hour(
    session: AsyncSession,
    settings: Settings,
    archive_hour: datetime,
    result: ArchiveResult,
) -> int:
    now = datetime.now(UTC)
    hour = archive_hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    # This table is a replaceable hourly projection. Reprocessing with a newer selection
    # algorithm must remove facts that the new projection intentionally omitted.
    await session.execute(
        delete(ExternalRepositoryActivity).where(ExternalRepositoryActivity.period_start == hour)
    )
    if not result.repositories:
        await _record_archive_file(session, settings, hour, result, "completed", now)
        await session.commit()
        return 0
    deduped_candidates = {}
    for activity in result.repositories:
        if activity.full_name in deduped_candidates:
            existing_val = deduped_candidates[activity.full_name]
            existing_val["source_score"] = max(existing_val["source_score"], activity.weighted_events)
            continue
        owner, name = activity.full_name.split("/", 1)
        deduped_candidates[activity.full_name] = {
            "github_id": activity.github_id,
            "owner": owner,
            "name": name,
            "full_name": activity.full_name,
            "description": None,
            "primary_language": None,
            "topics": [],
            "classification": "unclassified",
            "classification_confidence": 0,
            "rejection_reason": "metadata probe required",
            "stars": 0,
            "forks": 0,
            "pushed_at": None,
            "archived": False,
            "is_fork": False,
            "source": "gh_archive",
            "source_score": activity.weighted_events,
            "trend_score": 0.0,
            "trend_components": {},
            "tier": "candidate",
            "eligible": True,
            "discovered_at": now,
            "last_seen_at": now,
            "next_refresh_at": now,
        }
    candidate_values = list(deduped_candidates.values())

    # Check for candidates that already exist by full_name (avoid full_name key violation)
    existing_candidates = list(
        (
            await session.scalars(
                select(RepositoryCandidate).where(
                    RepositoryCandidate.full_name.in_([v["full_name"] for v in candidate_values])
                )
            )
        ).all()
    )
    existing_by_name = {c.full_name: c for c in existing_candidates}

    new_candidate_values = []
    for val in candidate_values:
        existing = existing_by_name.get(val["full_name"])
        if existing:
            existing.last_seen_at = now
            existing.source_score = max(existing.source_score, val["source_score"])
            if existing.github_id != val["github_id"]:
                existing.github_id = val["github_id"]
        else:
            new_candidate_values.append(val)

    if new_candidate_values:
        candidates = insert(RepositoryCandidate).values(new_candidate_values)
        await session.execute(
            candidates.on_conflict_do_update(
                index_elements=[RepositoryCandidate.github_id],
                set_={
                    "owner": candidates.excluded.owner,
                    "name": candidates.excluded.name,
                    "full_name": candidates.excluded.full_name,
                    "last_seen_at": candidates.excluded.last_seen_at,
                    "source_score": func.greatest(
                        RepositoryCandidate.source_score, candidates.excluded.source_score
                    ),
                },
            )
        )
    await session.flush()

    all_matched = list(
        (
            await session.scalars(
                select(RepositoryCandidate).where(
                    RepositoryCandidate.full_name.in_([act.full_name for act in result.repositories])
                )
            )
        ).all()
    )
    ids = {}
    for c in all_matched:
        ids[c.github_id] = c.id
        ids[c.full_name] = c.id

    activities = insert(ExternalRepositoryActivity).values(
        [
            {
                "candidate_id": ids.get(activity.github_id) or ids[activity.full_name],
                "period_start": hour,
                "star_events": activity.star_events,
                "fork_events": activity.fork_events,
                "push_events": activity.push_events,
                "pull_request_events": activity.pull_request_events,
                "issue_events": activity.issue_events,
                "release_events": activity.release_events,
                "weighted_events": activity.weighted_events,
            }
            for activity in result.repositories
            if activity.github_id in ids or activity.full_name in ids
        ]
    )
    await session.execute(
        activities.on_conflict_do_update(
            index_elements=[
                ExternalRepositoryActivity.candidate_id,
                ExternalRepositoryActivity.period_start,
            ],
            set_={
                "star_events": activities.excluded.star_events,
                "fork_events": activities.excluded.fork_events,
                "push_events": activities.excluded.push_events,
                "pull_request_events": activities.excluded.pull_request_events,
                "issue_events": activities.excluded.issue_events,
                "release_events": activities.excluded.release_events,
                "weighted_events": activities.excluded.weighted_events,
            },
        )
    )
    collection = await ensure_default_collection(session, settings)
    memberships = insert(CollectionMembership).values(
        [
            {
                "collection_id": collection.id,
                "candidate_id": candidate_id,
                "source": "gh_archive",
                "score": 0.0,
                "selected": False,
            }
            for candidate_id in ids.values()
        ]
    )
    await session.execute(
        memberships.on_conflict_do_nothing(
            index_elements=[
                CollectionMembership.collection_id,
                CollectionMembership.candidate_id,
            ]
        )
    )
    await _record_archive_file(session, settings, hour, result, "completed", now)
    await session.commit()
    log.info(
        "gh_archive_hour_completed",
        archive_hour=hour.isoformat(),
        repositories=len(result.repositories),
        events=result.event_count,
        compressed_bytes=result.compressed_bytes,
    )
    return len(result.repositories)


async def _record_archive_file(
    session: AsyncSession,
    settings: Settings,
    hour: datetime,
    result: ArchiveResult,
    status: str,
    now: datetime,
) -> None:
    statement = insert(GhArchiveFile).values(
        archive_hour=hour,
        algorithm_version=settings.gh_archive_algorithm_version,
        status=status,
        repository_count=len(result.repositories),
        event_count=result.event_count,
        compressed_bytes=result.compressed_bytes,
        processed_at=now,
        last_error=None,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[GhArchiveFile.archive_hour],
            set_={
                "status": statement.excluded.status,
                "algorithm_version": statement.excluded.algorithm_version,
                "repository_count": statement.excluded.repository_count,
                "event_count": statement.excluded.event_count,
                "compressed_bytes": statement.excluded.compressed_bytes,
                "processed_at": statement.excluded.processed_at,
                "last_error": None,
            },
        )
    )


def percentile_ranks(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [1.0]
    ordered = sorted((value, index) for index, value in enumerate(values) if value > 0)
    result = [0.0] * len(values)
    if not ordered:
        return result
    if len(ordered) == 1:
        result[ordered[0][1]] = 1.0
        return result
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        average_rank = (cursor + end + 1) / 2 / len(ordered)
        for _, original_index in ordered[cursor:end]:
            result[original_index] = average_rank
        cursor = end
    return result


async def reconcile_collection(
    session: AsyncSession, settings: Settings
) -> tuple[list[int], int, list[int]]:
    collection = await ensure_default_collection(session, settings)
    cutoff = datetime.now(UTC) - timedelta(days=7)
    activity = (
        select(
            ExternalRepositoryActivity.candidate_id.label("candidate_id"),
            func.sum(ExternalRepositoryActivity.star_events).label("stars"),
            func.sum(ExternalRepositoryActivity.fork_events).label("forks"),
            func.sum(ExternalRepositoryActivity.push_events).label("pushes"),
            func.sum(ExternalRepositoryActivity.pull_request_events).label("prs"),
            func.sum(ExternalRepositoryActivity.issue_events).label("issues"),
            func.sum(ExternalRepositoryActivity.release_events).label("releases"),
        )
        .where(ExternalRepositoryActivity.period_start >= cutoff)
        .group_by(ExternalRepositoryActivity.candidate_id)
        .subquery()
    )
    archive_signal = (
        (RepositoryCandidate.source != "gh_archive")
        | (RepositoryCandidate.stars >= settings.discovery_min_stars)
        | (func.coalesce(activity.c.stars, 0) >= 2)
        | (func.coalesce(activity.c.forks, 0) >= 2)
    )
    rows = (
        await session.execute(
            select(
                RepositoryCandidate,
                func.coalesce(activity.c.stars, 0),
                func.coalesce(activity.c.forks, 0),
                func.coalesce(activity.c.pushes, 0),
                func.coalesce(activity.c.prs, 0),
                func.coalesce(activity.c.issues, 0),
                func.coalesce(activity.c.releases, 0),
                CollectionMembership,
            )
            .join(
                CollectionMembership,
                CollectionMembership.candidate_id == RepositoryCandidate.id,
            )
            .outerjoin(activity, activity.c.candidate_id == RepositoryCandidate.id)
            .where(
                CollectionMembership.collection_id == collection.id,
                RepositoryCandidate.eligible.is_(True),
                archive_signal,
            )
            .order_by(
                func.coalesce(activity.c.stars, 0).desc(),
                RepositoryCandidate.stars.desc(),
                RepositoryCandidate.last_seen_at.desc(),
            )
            .limit(collection.candidate_limit)
        )
    ).all()
    if not rows:
        await session.commit()
        return [], 0, []
    components = [[float(row[index]) for row in rows] for index in range(1, 7)]
    popularity = [math.log1p(max(row[0].stars, 0)) for row in rows]
    ranked = [percentile_ranks(values) for values in [*components, popularity]]
    scored: list[tuple[float, RepositoryCandidate, dict[str, Any], CollectionMembership]] = []
    for index, row in enumerate(rows):
        candidate = row[0]
        star_rank, fork_rank, push_rank, pr_rank, issue_rank, release_rank, popularity_rank = (
            values[index] for values in ranked
        )
        score = 100 * (
            star_rank * 0.5
            + fork_rank * 0.12
            + push_rank * 0.03
            + pr_rank * 0.12
            + issue_rank * 0.05
            + release_rank * 0.1
            + popularity_rank * 0.08
        )
        detail = {
            "window_days": 7,
            "star_events": int(row[1]),
            "fork_events": int(row[2]),
            "push_events": int(row[3]),
            "pull_request_events": int(row[4]),
            "issue_events": int(row[5]),
            "release_events": int(row[6]),
            "provisional": sum(int(row[value_index]) for value_index in range(1, 7)) == 0,
        }
        scored.append((round(score, 2), candidate, detail, row[7]))
    scored.sort(key=lambda item: item[0], reverse=True)
    classified = [item for item in scored if item[1].classification in SOFTWARE_CLASSIFICATIONS]
    selected_ids = {
        candidate.id
        for _, candidate, _, _ in classified[: collection.active_limit]
        if candidate.tier != "pinned"
    }
    selected_ids.update(candidate.id for _, candidate, _, _ in scored if candidate.tier == "pinned")
    probe_ids = [
        candidate.id
        for _, candidate, _, _ in scored
        if candidate.classification == "unclassified" and candidate.source == "gh_archive"
    ][: settings.discovery_probe_limit_per_reconcile]
    now = datetime.now(UTC)
    newly_active: list[int] = []
    for rank, (score, candidate, detail, membership) in enumerate(scored, start=1):
        was_active = candidate.tier in {"active", "pinned"}
        selected = candidate.id in selected_ids
        candidate.trend_score = score
        candidate.trend_components = detail
        if candidate.tier != "pinned":
            candidate.tier = "active" if selected else "candidate"
        if selected and not was_active:
            candidate.promoted_at = now
            newly_active.append(candidate.id)
        candidate.next_refresh_at = (
            now if selected else now + timedelta(hours=settings.collector_candidate_refresh_hours)
        )
        membership.score = score
        membership.rank = rank
        membership.selected = selected
        membership.last_ranked_at = now
    if selected_ids:
        await session.execute(
            update(RepositoryCandidate)
            .where(
                RepositoryCandidate.tier == "active",
                RepositoryCandidate.id.not_in(selected_ids),
            )
            .values(tier="candidate")
        )
        await session.execute(
            update(CollectionMembership)
            .where(
                CollectionMembership.collection_id == collection.id,
                CollectionMembership.selected.is_(True),
                CollectionMembership.candidate_id.not_in(selected_ids),
            )
            .values(selected=False, rank=None, last_ranked_at=now)
        )
        await session.execute(
            update(IngestionJob)
            .where(
                IngestionJob.job_type == "hydrate_repository",
                IngestionJob.status == "queued",
                IngestionJob.candidate_id.not_in(selected_ids),
            )
            .values(
                status="cancelled",
                finished_at=now,
                updated_at=now,
                last_error="candidate left the active collection before hydration",
            )
        )
    collection.updated_at = now
    await session.commit()
    log.info(
        "collection_reconciled",
        candidates=len(scored),
        selected=len(selected_ids),
        newly_active=len(newly_active),
        probes=len(probe_ids),
    )
    return newly_active, len(selected_ids), probe_ids
