from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from dateutil.parser import isoparse
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CollectionMembership,
    Commit,
    Contributor,
    Issue,
    PullRequest,
    Release,
    Repository,
    RepositoryCandidate,
    RepositoryContributor,
    RepositoryLanguage,
    RepositorySnapshot,
    RepositorySyncState,
    RepositoryTopic,
)
from app.github.client import GitHubClient
from app.services.discovery import classify_repository, ensure_default_collection

log = structlog.get_logger()


def dt(value: str | None) -> datetime | None:
    return isoparse(value) if value else None


class RepositoryIngester:
    """Bounded and incremental repository hydration using page-level PostgreSQL upserts."""

    def __init__(
        self, session: AsyncSession, github: GitHubClient, settings: Settings | None = None
    ) -> None:
        self.session = session
        self.github = github
        self.settings = settings or get_settings()

    async def ingest(self, full_name: str, mode: str = "full") -> Repository:
        if full_name.count("/") != 1:
            raise ValueError("repository must use owner/name format")
        if mode not in {"full", "refresh", "metadata"}:
            raise ValueError("mode must be full, refresh, or metadata")
        started_at = datetime.now(UTC)
        payload = await self.github.get_json(f"/repos/{full_name}")
        repo = await self._upsert_repository(payload)
        await self.session.flush()
        await self._link_candidate(repo, payload)
        previous_ingestion = repo.last_ingested_at
        await self._daily_snapshot(repo)
        if mode != "metadata":
            since = previous_ingestion or started_at - timedelta(
                days=self.settings.ingestion_bootstrap_days
            )
            await self._commits(repo, since)
            await self._issues(repo, since)
            await self._pull_requests(repo, since)
            await self._releases(
                repo,
                started_at - timedelta(days=self.settings.ingestion_release_days),
            )
            if await self._resource_due(repo.id, "contributors", days=7):
                contributor_count = await self._contributors(repo)
                await self._update_snapshot_contributors(repo.id, contributor_count)
            if await self._resource_due(repo.id, "metadata", days=7):
                await self._metadata(repo, payload.get("topics", []))
            repo.last_ingested_at = datetime.now(UTC)
        await self.session.commit()
        log.info(
            "repository_ingested",
            repository=repo.full_name,
            mode=mode,
            incremental_since=str(previous_ingestion),
            elapsed_seconds=round((datetime.now(UTC) - started_at).total_seconds(), 2),
        )
        return repo

    async def _upsert_repository(self, payload: dict[str, Any]) -> Repository:
        repo = await self.session.scalar(
            select(Repository).where(Repository.github_id == payload["id"])
        )
        values = {
            "owner": payload["owner"]["login"],
            "name": payload["name"],
            "full_name": payload["full_name"],
            "description": payload.get("description"),
            "created_at": dt(payload["created_at"]),
            "updated_at": dt(payload["updated_at"]),
            "pushed_at": dt(payload.get("pushed_at")),
            "stars": payload["stargazers_count"],
            "forks": payload["forks_count"],
            "watchers": payload.get("subscribers_count", 0),
            "open_issues": payload["open_issues_count"],
            "default_branch": payload["default_branch"],
            "primary_language": payload.get("language"),
            "license": (payload.get("license") or {}).get("spdx_id"),
            "archived": payload["archived"],
        }
        if repo is None:
            repo = Repository(github_id=payload["id"], **values)
            self.session.add(repo)
        else:
            for key, value in values.items():
                setattr(repo, key, value)
        return repo

    async def _link_candidate(self, repo: Repository, payload: dict[str, Any]) -> None:
        classification = classify_repository(payload)
        topics = sorted(
            {
                str(topic).strip().casefold().replace("_", "-")
                for topic in payload.get("topics", [])
                if str(topic).strip()
            }
        )
        candidate = await self.session.scalar(
            select(RepositoryCandidate).where(RepositoryCandidate.github_id == repo.github_id)
        )
        if candidate is None:
            now = datetime.now(UTC)
            candidate = RepositoryCandidate(
                github_id=repo.github_id,
                repository_id=repo.id,
                owner=repo.owner,
                name=repo.name,
                full_name=repo.full_name,
                description=repo.description,
                primary_language=repo.primary_language,
                topics=topics,
                classification=classification.category,
                classification_confidence=classification.confidence,
                rejection_reason=classification.reason,
                stars=repo.stars,
                forks=repo.forks,
                pushed_at=repo.pushed_at,
                archived=repo.archived,
                is_fork=bool(payload.get("fork")),
                source="manual",
                source_score=0,
                trend_score=0,
                trend_components={},
                tier="pinned",
                eligible=True,
                discovered_at=now,
                last_seen_at=now,
                promoted_at=now,
                next_refresh_at=now + timedelta(hours=self.settings.collector_active_refresh_hours),
            )
            self.session.add(candidate)
        else:
            candidate.repository_id = repo.id
            candidate.owner = repo.owner
            candidate.name = repo.name
            candidate.full_name = repo.full_name
            candidate.description = repo.description
            candidate.primary_language = repo.primary_language
            candidate.topics = topics
            candidate.classification = classification.category
            candidate.classification_confidence = classification.confidence
            candidate.rejection_reason = classification.reason
            candidate.stars = repo.stars
            candidate.forks = repo.forks
            candidate.pushed_at = repo.pushed_at
            candidate.archived = repo.archived
            candidate.eligible = not repo.archived and (
                classification.eligible or candidate.tier == "pinned"
            )
            candidate.last_seen_at = datetime.now(UTC)
            candidate.next_refresh_at = datetime.now(UTC) + timedelta(
                hours=self.settings.collector_active_refresh_hours
            )
        await self.session.flush()
        collection = await ensure_default_collection(self.session, self.settings)
        membership = insert(CollectionMembership).values(
            collection_id=collection.id,
            candidate_id=candidate.id,
            source=candidate.source,
            score=candidate.trend_score,
            selected=candidate.tier in {"active", "pinned"},
            last_ranked_at=datetime.now(UTC),
        )
        await self.session.execute(
            membership.on_conflict_do_update(
                index_elements=[
                    CollectionMembership.collection_id,
                    CollectionMembership.candidate_id,
                ],
                set_={
                    "source": membership.excluded.source,
                    "selected": membership.excluded.selected,
                },
            )
        )

    async def _daily_snapshot(self, repo: Repository) -> None:
        now = datetime.now(UTC)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        snapshot = await self.session.scalar(
            select(RepositorySnapshot).where(
                RepositorySnapshot.repository_id == repo.id,
                RepositorySnapshot.captured_at >= day_start,
            )
        )
        values = {
            "captured_at": now,
            "stars": repo.stars,
            "forks": repo.forks,
            "open_issues": repo.open_issues,
            "watchers": repo.watchers,
        }
        if snapshot is None:
            self.session.add(
                RepositorySnapshot(repository_id=repo.id, contributor_count=None, **values)
            )
        else:
            for key, value in values.items():
                setattr(snapshot, key, value)

    async def _update_snapshot_contributors(self, repository_id: int, count: int) -> None:
        snapshot = await self.session.scalar(
            select(RepositorySnapshot)
            .where(RepositorySnapshot.repository_id == repository_id)
            .order_by(RepositorySnapshot.captured_at.desc())
            .limit(1)
        )
        if snapshot:
            snapshot.contributor_count = count

    async def _resource_due(self, repository_id: int, resource: str, days: int) -> bool:
        state = await self.session.get(RepositorySyncState, (repository_id, resource))
        return (
            not state
            or not state.last_success_at
            or state.last_success_at < datetime.now(UTC) - timedelta(days=days)
        )

    async def _mark_resource(self, repository_id: int, resource: str) -> None:
        now = datetime.now(UTC)
        state = await self.session.get(RepositorySyncState, (repository_id, resource))
        if state is None:
            state = RepositorySyncState(
                repository_id=repository_id,
                resource=resource,
                watermark=now,
                last_success_at=now,
                next_sync_at=now + timedelta(days=7),
                updated_at=now,
            )
            self.session.add(state)
        else:
            state.watermark = now
            state.last_success_at = now
            state.next_sync_at = now + timedelta(days=7)
            state.last_error = None
            state.updated_at = now

    async def _contributors(self, repo: Repository) -> int:
        total = 0
        async for page in self.github.paginate_pages(
            f"/repos/{repo.full_name}/contributors",
            {"anon": "false"},
            max_items=self.settings.ingestion_contributor_limit,
        ):
            rows = [
                {
                    "github_id": item["id"],
                    "login": item["login"],
                    "avatar_url": item.get("avatar_url"),
                    "html_url": item.get("html_url"),
                    "contributor_type": item.get("type"),
                }
                for item in page
                if item.get("id") is not None and item.get("login")
            ]
            if not rows:
                continue
            total += len(rows)
            statement = insert(Contributor).values(rows)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Contributor.github_id],
                    set_={
                        "login": statement.excluded.login,
                        "avatar_url": statement.excluded.avatar_url,
                        "html_url": statement.excluded.html_url,
                        "contributor_type": statement.excluded.contributor_type,
                    },
                )
            )
            await self.session.flush()
            contributors = (
                await self.session.execute(
                    select(Contributor.github_id, Contributor.id).where(
                        Contributor.github_id.in_([row["github_id"] for row in rows])
                    )
                )
            ).all()
            ids = {github_id: contributor_id for github_id, contributor_id in contributors}
            contributions = insert(RepositoryContributor).values(
                [
                    {
                        "repository_id": repo.id,
                        "contributor_id": ids[item["id"]],
                        "contributions": item["contributions"],
                        "last_seen_at": datetime.now(UTC),
                    }
                    for item in page
                    if item.get("id") in ids
                ]
            )
            await self.session.execute(
                contributions.on_conflict_do_update(
                    index_elements=[
                        RepositoryContributor.repository_id,
                        RepositoryContributor.contributor_id,
                    ],
                    set_={
                        "contributions": contributions.excluded.contributions,
                        "last_seen_at": contributions.excluded.last_seen_at,
                    },
                )
            )
        await self._mark_resource(repo.id, "contributors")
        return total

    async def _commits(self, repo: Repository, since: datetime) -> None:
        async for page in self.github.paginate_pages(
            f"/repos/{repo.full_name}/commits",
            {"since": since.isoformat()},
            max_items=self.settings.ingestion_commit_limit,
        ):
            rows = []
            for item in page:
                author = item.get("author") or {}
                commit = item["commit"]
                rows.append(
                    {
                        "repository_id": repo.id,
                        "sha": item["sha"],
                        "author_login": author.get("login") or commit.get("author", {}).get("name"),
                        "committed_at": dt(commit["author"]["date"]),
                    }
                )
            statement = insert(Commit).values(rows)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Commit.repository_id, Commit.sha],
                    set_={
                        "author_login": statement.excluded.author_login,
                        "committed_at": statement.excluded.committed_at,
                    },
                )
            )
        await self._mark_resource(repo.id, "commits")

    async def _issues(self, repo: Repository, since: datetime) -> None:
        params: dict[str, Any] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since.isoformat(),
        }
        async for page in self.github.paginate_pages(
            f"/repos/{repo.full_name}/issues",
            params,
            max_items=self.settings.ingestion_issue_limit,
        ):
            rows = [
                {
                    "repository_id": repo.id,
                    "number": item["number"],
                    "author_login": (item.get("user") or {}).get("login"),
                    "state": item["state"],
                    "created_at": dt(item["created_at"]),
                    "updated_at": dt(item["updated_at"]),
                    "closed_at": dt(item.get("closed_at")),
                    "comments": item["comments"],
                    "labels": [
                        {"name": label["name"], "color": label["color"]}
                        for label in item.get("labels", [])
                    ],
                }
                for item in page
                if "pull_request" not in item
            ]
            if not rows:
                continue
            statement = insert(Issue).values(rows)
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Issue.repository_id, Issue.number],
                    set_={
                        "author_login": statement.excluded.author_login,
                        "state": statement.excluded.state,
                        "updated_at": statement.excluded.updated_at,
                        "closed_at": statement.excluded.closed_at,
                        "comments": statement.excluded.comments,
                        "labels": statement.excluded.labels,
                    },
                )
            )
        await self._mark_resource(repo.id, "issues")

    async def _pull_requests(self, repo: Repository, since: datetime) -> None:
        stop = False
        async for page in self.github.paginate_pages(
            f"/repos/{repo.full_name}/pulls",
            {"state": "all", "sort": "updated", "direction": "desc"},
            max_items=self.settings.ingestion_pull_request_limit,
        ):
            rows = []
            for item in page:
                updated = dt(item["updated_at"])
                if updated and updated < since:
                    stop = True
                    break
                rows.append(
                    {
                        "repository_id": repo.id,
                        "number": item["number"],
                        "author_login": (item.get("user") or {}).get("login"),
                        "state": item["state"],
                        "created_at": dt(item["created_at"]),
                        "updated_at": updated,
                        "closed_at": dt(item.get("closed_at")),
                        "merged_at": dt(item.get("merged_at")),
                        "additions": None,
                        "deletions": None,
                        "changed_files": None,
                    }
                )
            if rows:
                statement = insert(PullRequest).values(rows)
                await self.session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[PullRequest.repository_id, PullRequest.number],
                        set_={
                            "author_login": statement.excluded.author_login,
                            "state": statement.excluded.state,
                            "updated_at": statement.excluded.updated_at,
                            "closed_at": statement.excluded.closed_at,
                            "merged_at": statement.excluded.merged_at,
                        },
                    )
                )
            if stop:
                break
        await self._mark_resource(repo.id, "pull_requests")

    async def _releases(self, repo: Repository, since: datetime) -> None:
        stop = False
        async for page in self.github.paginate_pages(
            f"/repos/{repo.full_name}/releases",
            max_items=self.settings.ingestion_release_limit,
        ):
            rows = []
            for item in page:
                published = dt(item.get("published_at")) or dt(item["created_at"])
                if published and published < since:
                    stop = True
                    break
                rows.append(
                    {
                        "repository_id": repo.id,
                        "github_id": item["id"],
                        "tag": item["tag_name"],
                        "created_at": dt(item["created_at"]),
                        "published_at": dt(item.get("published_at")),
                        "prerelease": item["prerelease"],
                        "draft": item["draft"],
                    }
                )
            if rows:
                statement = insert(Release).values(rows)
                await self.session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[Release.repository_id, Release.github_id],
                        set_={
                            "tag": statement.excluded.tag,
                            "published_at": statement.excluded.published_at,
                            "prerelease": statement.excluded.prerelease,
                            "draft": statement.excluded.draft,
                        },
                    )
                )
            if stop:
                break
        await self._mark_resource(repo.id, "releases")

    async def _metadata(self, repo: Repository, topics: list[str]) -> None:
        languages = await self.github.get_json(f"/repos/{repo.full_name}/languages")
        await self.session.execute(
            delete(RepositoryLanguage).where(RepositoryLanguage.repository_id == repo.id)
        )
        await self.session.execute(
            delete(RepositoryTopic).where(RepositoryTopic.repository_id == repo.id)
        )
        if languages:
            await self.session.execute(
                insert(RepositoryLanguage).values(
                    [
                        {"repository_id": repo.id, "language": language, "bytes": size}
                        for language, size in languages.items()
                    ]
                )
            )
        if topics:
            await self.session.execute(
                insert(RepositoryTopic).values(
                    [{"repository_id": repo.id, "topic": topic} for topic in dict.fromkeys(topics)]
                )
            )
        await self._mark_resource(repo.id, "metadata")
