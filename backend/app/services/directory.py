from collections import defaultdict
from datetime import UTC, datetime, timedelta
import math
from typing import Any

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    ExternalRepositoryActivity,
    Repository,
    RepositoryCandidate,
    RepositorySearchDocument,
    RepositorySignalSnapshot,
)
from app.github.client import GitHubClient

log = structlog.get_logger()

SOFTWARE_CLASSIFICATIONS = {"library", "framework", "developer_tool", "software"}

STAR_BANDS = [
    (0, 10),
    (11, 50),
    (51, 200),
    (201, 1000),
    (1001, 5000),
    (5001, 10000000),
]


def calculate_selection_score(
    repo: CatalogRepository,
    activity_count: int = 0,
) -> float:
    """Calculate multi-factor selection score (0-100) based on activity, popularity,

    freshness, and maintenance.
    """
    now = datetime.now(UTC)

    # Popularity (0-100)
    stars = repo.stars or 0
    forks = repo.forks or 0
    popularity = min(100.0, math.log1p(stars) * 8.0 + math.log1p(forks) * 4.0)

    # Freshness (0-100)
    freshness = 20.0
    if repo.pushed_at:
        days = max(0.0, (now - repo.pushed_at).total_seconds() / 86400)
        freshness = max(0.0, 100.0 - days * 1.0)

    # Activity (0-100)
    activity = min(100.0, 20.0 + (activity_count * 2.5))

    # Maintenance (0-100)
    maintenance = 50.0
    if repo.license:
        maintenance += 20.0
    if repo.description and len(repo.description) > 20:
        maintenance += 15.0
    if repo.topics and len(repo.topics) >= 2:
        maintenance += 15.0

    # Weighted score
    score = 0.35 * activity + 0.30 * popularity + 0.20 * freshness + 0.15 * maintenance
    return round(score, 2)


async def reconcile_directory_and_cohort(
    session: AsyncSession,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Select exactly top 10,000 active directory members with language diversity cap (25%),

    top 500 deep cohort members, and enforce rolling 50K candidate pool bounds.
    """
    cfg = settings or get_settings()
    target_directory_size = cfg.directory_limit
    max_per_language = max(1, int(target_directory_size * cfg.directory_language_cap))
    target_deep_size = cfg.deep_cohort_limit

    # 1. Fetch all eligible catalog repositories
    stmt = (
        select(CatalogRepository)
        .where(
            CatalogRepository.is_fork.is_(False),
            CatalogRepository.archived.is_(False),
            CatalogRepository.classification.in_(SOFTWARE_CLASSIFICATIONS),
        )
        .order_by(
            CatalogRepository.selection_score.desc(),
            CatalogRepository.stars.desc(),
            CatalogRepository.pushed_at.desc().nullslast(),
        )
    )
    candidates = list((await session.scalars(stmt)).all())

    # 2. Select Directory Members enforcing Diversity Cap (25% per language)
    selected_directory_ids: set[int] = set()
    language_counts: dict[str, int] = defaultdict(int)

    for repo in candidates:
        if len(selected_directory_ids) >= target_directory_size:
            break
        lang = repo.primary_language or "Unknown"
        if language_counts[lang] < max_per_language:
            selected_directory_ids.add(repo.github_id)
            language_counts[lang] += 1

    # If diversity cap left open slots, fill with next best repos
    if len(selected_directory_ids) < target_directory_size:
        for repo in candidates:
            if len(selected_directory_ids) >= target_directory_size:
                break
            selected_directory_ids.add(repo.github_id)

    # 3. Select Deep Cohort (Top 500 from directory)
    # Highest selection score or already hydrated repos
    deep_cohort_candidates = sorted(
        [r for r in candidates if r.github_id in selected_directory_ids],
        key=lambda r: (r.repository_id is not None, r.selection_score, r.stars),
        reverse=True,
    )
    selected_deep_ids = {r.github_id for r in deep_cohort_candidates[:target_deep_size]}

    # 4. Batch update catalog memberships
    # Reset flags
    await session.execute(
        update(CatalogRepository)
        .values(
            is_directory=False,
            is_deep=False,
            tier="candidate",
        )
        .execution_options(synchronize_session=False)
    )

    if selected_directory_ids:
        await session.execute(
            update(CatalogRepository)
            .where(CatalogRepository.github_id.in_(selected_directory_ids))
            .values(is_directory=True, tier="directory")
            .execution_options(synchronize_session=False)
        )

    if selected_deep_ids:
        await session.execute(
            update(CatalogRepository)
            .where(CatalogRepository.github_id.in_(selected_deep_ids))
            .values(is_deep=True, tier="deep")
            .execution_options(synchronize_session=False)
        )

    # 5. Prune candidate pool beyond 50,000 bounds and 90-day retention
    retention_cutoff = datetime.now(UTC) - timedelta(days=cfg.candidate_retention_days)
    prune_stmt = (
        delete(CatalogRepository)
        .where(
            CatalogRepository.is_directory.is_(False),
            CatalogRepository.is_deep.is_(False),
            CatalogRepository.last_observed_at < retention_cutoff,
        )
        .execution_options(synchronize_session=False)
    )
    prune_result = await session.execute(prune_stmt)
    pruned_count = int(getattr(prune_result, "rowcount", 0) or 0)

    # Enforce 50,000 candidate pool cap
    total_candidates = await session.scalar(
        select(func.count()).select_from(CatalogRepository)
    )
    excess = max(0, int(total_candidates or 0) - cfg.candidate_pool_limit)
    if excess > 0:
        excess_ids = (
            await session.scalars(
                select(CatalogRepository.github_id)
                .where(
                    CatalogRepository.is_directory.is_(False),
                    CatalogRepository.is_deep.is_(False),
                )
                .order_by(CatalogRepository.selection_score.asc())
                .limit(excess)
            )
        ).all()
        if excess_ids:
            await session.execute(
                delete(CatalogRepository)
                .where(CatalogRepository.github_id.in_(excess_ids))
                .execution_options(synchronize_session=False)
            )
            pruned_count += len(excess_ids)

    await session.commit()
    summary = {
        "directory_count": len(selected_directory_ids),
        "deep_cohort_count": len(selected_deep_ids),
        "languages_represented": len(language_counts),
        "pruned_candidates": pruned_count,
    }
    log.info("directory_reconciliation_complete", **summary)
    return summary


async def discover_github_sharded(
    session: AsyncSession,
    github: GitHubClient,
    settings: Settings,
    language: str,
    star_min: int = 0,
    star_max: int = 10,
    pushed_within_days: int = 90,
) -> int:
    """Discover repositories in sharded search bands by language and star range."""
    now = datetime.now(UTC)
    cutoff = (now - timedelta(days=pushed_within_days)).strftime("%Y-%m-%d")
    query = f"language:{language} stars:{star_min}..{star_max} pushed:>={cutoff} fork:false"

    log.info("sharded_search_start", language=language, stars=f"{star_min}..{star_max}")
    items = await github.search_repositories(query, max_results=100, sort="updated")

    discovered = 0
    for payload in items:
        gid = payload["id"]
        full_name = payload["full_name"]
        topics = [
            str(t).strip().casefold().replace("_", "-")
            for t in payload.get("topics", [])
            if str(t).strip()
        ]

        stmt = (
            insert(CatalogRepository)
            .values(
                github_id=gid,
                owner=payload["owner"]["login"],
                name=payload["name"],
                full_name=full_name,
                description=payload.get("description"),
                primary_language=payload.get("language") or language,
                license=(payload.get("license") or {}).get("spdx_id"),
                default_branch=payload.get("default_branch", "main"),
                stars=payload.get("stargazers_count", 0),
                forks=payload.get("forks_count", 0),
                watchers=payload.get("watchers_count", 0),
                open_issues=payload.get("open_issues_count", 0),
                created_at=datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00")),
                pushed_at=datetime.fromisoformat(payload["pushed_at"].replace("Z", "+00:00"))
                if payload.get("pushed_at")
                else None,
                archived=payload.get("archived", False),
                is_fork=payload.get("fork", False),
                tier="candidate",
                is_directory=False,
                is_deep=False,
                classification="software",
                classification_confidence=0.8,
                topics=topics,
                activity_score=0.0,
                popularity_score=min(100.0, payload.get("stargazers_count", 0) * 1.5),
                freshness_score=80.0,
                maintenance_score=50.0,
                selection_score=25.0,
                scout_eligible=True,
                last_discovered_at=now,
                last_observed_at=now,
                provenance={"source": "github_search_sharded", "observed_at": now.isoformat()},
            )
            .on_conflict_do_update(
                index_elements=[CatalogRepository.github_id],
                set_={
                    "stars": payload.get("stargazers_count", 0),
                    "forks": payload.get("forks_count", 0),
                    "pushed_at": datetime.fromisoformat(payload["pushed_at"].replace("Z", "+00:00"))
                    if payload.get("pushed_at")
                    else None,
                    "last_observed_at": now,
                },
            )
        )
        await session.execute(stmt)

        # Upsert search document
        doc_stmt = (
            insert(RepositorySearchDocument)
            .values(
                github_id=gid,
                full_name=full_name,
                name=payload["name"],
                owner=payload["owner"]["login"],
                description=payload.get("description"),
                topics_text=" ".join(topics),
                primary_language=payload.get("language") or language,
                license=(payload.get("license") or {}).get("spdx_id"),
                readme_text="",
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[RepositorySearchDocument.github_id],
                set_={
                    "description": payload.get("description"),
                    "topics_text": " ".join(topics),
                    "updated_at": now,
                },
            )
        )
        await session.execute(doc_stmt)
        discovered += 1

    await session.commit()
    return discovered
