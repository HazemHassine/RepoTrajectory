from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.metrics import (
    HealthInput,
    MomentumInput,
    concentration_metrics,
    health_score,
    momentum_score,
    ratio_change,
)
from app.db.models import (
    Commit,
    Issue,
    MetricSnapshot,
    PullRequest,
    Release,
    Repository,
    RepositoryContributor,
    RepositorySnapshot,
)


def is_bot(login: str | None) -> bool:
    if not login:
        return False
    normalized = login.casefold()
    return normalized.endswith("[bot]") or normalized in {
        "dependabot",
        "dependabot-preview",
        "github-actions",
        "pre-commit-ci",
    }


async def calculate_metrics(
    session: AsyncSession, repo: Repository, window_days: int = 30
) -> MetricSnapshot:
    now, start = datetime.now(UTC), datetime.now(UTC) - timedelta(days=window_days)
    previous = start - timedelta(days=window_days)

    async def count(model: Any, date_col: Any, begin: datetime, end: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(model)
            .where(model.repository_id == repo.id, date_col >= begin, date_col < end)
        )
        return int(await session.scalar(stmt) or 0)

    async def contributions(begin: datetime, end: datetime) -> tuple[list[int], int, int]:
        rows = (
            await session.execute(
                select(Commit.author_login, func.count(Commit.sha))
                .where(
                    Commit.repository_id == repo.id,
                    Commit.committed_at >= begin,
                    Commit.committed_at < end,
                )
                .group_by(Commit.author_login)
            )
        ).all()
        human = [int(value) for login, value in rows if not is_bot(login)]
        automated = sum(int(value) for login, value in rows if is_bot(login))
        return human, sum(human), automated

    recent_contributions, commits, automated_commits = await contributions(start, now)
    _, previous_commits, previous_automated_commits = await contributions(previous, start)
    prs = await count(PullRequest, PullRequest.created_at, start, now)
    previous_prs = await count(PullRequest, PullRequest.created_at, previous, start)
    releases = int(
        await session.scalar(
            select(func.count())
            .select_from(Release)
            .where(
                Release.repository_id == repo.id,
                Release.published_at >= start,
                Release.published_at < now,
                Release.draft.is_(False),
                Release.prerelease.is_(False),
            )
        )
        or 0
    )
    merged_prs = await count(PullRequest, PullRequest.merged_at, start, now)
    previous_merged_prs = await count(PullRequest, PullRequest.merged_at, previous, start)
    issues_opened = await count(Issue, Issue.created_at, start, now)
    issues_closed = await count(Issue, Issue.closed_at, start, now)
    previous_issues_closed = await count(Issue, Issue.closed_at, previous, start)
    active = len(recent_contributions)
    resolved_prs = (
        await session.scalars(
            select(PullRequest).where(
                PullRequest.repository_id == repo.id,
                PullRequest.closed_at >= start,
                PullRequest.closed_at < now,
            )
        )
    ).all()
    closed_issues = (
        await session.scalars(
            select(Issue).where(
                Issue.repository_id == repo.id,
                Issue.closed_at >= start,
                Issue.closed_at < now,
            )
        )
    ).all()
    merged = [item for item in resolved_prs if item.merged_at]
    merge_hours = [
        (x.merged_at - x.created_at).total_seconds() / 3600 for x in merged if x.merged_at
    ]
    issue_hours = [
        (x.closed_at - x.created_at).total_seconds() / 3600 for x in closed_issues if x.closed_at
    ]
    cumulative_contributions = list(
        (
            await session.scalars(
                select(RepositoryContributor.contributions).where(
                    RepositoryContributor.repository_id == repo.id
                )
            )
        ).all()
    )
    snapshots = (
        await session.scalars(
            select(RepositorySnapshot)
            .where(RepositorySnapshot.repository_id == repo.id)
            .order_by(RepositorySnapshot.captured_at)
        )
    ).all()
    older = next((x for x in reversed(snapshots) if x.captured_at <= start), None)
    star_growth = (repo.stars - older.stars) / max(older.stars, 1) if older else 0
    contributor_growth = (
        ((snapshots[-1].contributor_count or 0) - (older.contributor_count or 0))
        / max(older.contributor_count or 1, 1)
        if older and snapshots
        else 0
    )
    momentum, momentum_parts = momentum_score(
        MomentumInput(
            star_growth,
            contributor_growth,
            commits,
            previous_commits,
            prs,
            previous_prs,
            releases * 30 / window_days,
        ),
        growth_available=older is not None,
    )
    if commits + prs + releases == 0 and older is None:
        momentum = 0.0
        momentum_parts["commit_acceleration"] = 0.0
        momentum_parts["pr_acceleration"] = 0.0
    merge_rate = len(merged) / len(resolved_prs) if resolved_prs else 0
    health, health_parts = health_score(
        HealthInput(
            active,
            median(issue_hours) if issue_hours else None,
            median(merge_hours) if merge_hours else None,
            merge_rate,
            releases * 30 / window_days,
            commits * 7 / window_days,
        )
    )
    concentration = concentration_metrics(recent_contributions or cumulative_contributions)
    concentration_data: dict[str, object] = {
        **concentration,
        "basis": "recent_commits" if recent_contributions else "all_time_contributions",
    }
    last_commit_at = await session.scalar(
        select(func.max(Commit.committed_at)).where(Commit.repository_id == repo.id)
    )
    last_release_at = await session.scalar(
        select(func.max(Release.published_at)).where(
            Release.repository_id == repo.id,
            Release.draft.is_(False),
            Release.prerelease.is_(False),
        )
    )
    snapshot_span_days = (
        (snapshots[-1].captured_at - snapshots[0].captured_at).total_seconds() / 86400
        if len(snapshots) > 1
        else 0
    )
    evidence_events = commits + prs + issues_opened + releases
    confidence_score = min(
        100.0,
        25
        + min(evidence_events, 150) / 150 * 50
        + min(snapshot_span_days, window_days) / window_days * 25,
    )
    activity_change = ratio_change(commits, previous_commits)
    pr_change = ratio_change(prs, previous_prs)
    issue_change = ratio_change(issues_closed, previous_issues_closed)
    issue_balance = issues_closed - issues_opened
    days_since_commit = max(0, (now - last_commit_at).days) if last_commit_at else None
    days_since_release = max(0, (now - last_release_at).days) if last_release_at else None
    if repo.archived:
        status, status_tone = "Archived", "neutral"
    elif commits == 0 and prs == 0 and (days_since_commit is None or days_since_commit > 90):
        status, status_tone = "Dormant", "critical"
    elif momentum < 45 or activity_change < -0.25:
        status, status_tone = "Cooling", "warning"
    elif momentum >= 65 and health >= 65:
        status, status_tone = "Advancing", "positive"
    else:
        status, status_tone = "Stable", "neutral"
    metric = MetricSnapshot(
        repository_id=repo.id,
        calculated_at=now,
        window_days=window_days,
        momentum_score=momentum,
        health_score=health,
        bus_factor_risk=concentration["risk_score"],
        components={
            "methodology_version": 3,
            "momentum": momentum_parts,
            "health": health_parts,
            "concentration": concentration_data,
            "velocity": {
                "commits": commits,
                "previous_commits": previous_commits,
                "automated_commits": automated_commits,
                "previous_automated_commits": previous_automated_commits,
                "automation_share": round(
                    automated_commits / max(commits + automated_commits, 1), 4
                ),
                "commit_change": round(activity_change, 4),
                "pull_requests": prs,
                "previous_pull_requests": previous_prs,
                "pr_change": round(pr_change, 4),
                "merged_pull_requests": merged_prs,
                "previous_merged_pull_requests": previous_merged_prs,
                "issues_opened": issues_opened,
                "issues_closed": issues_closed,
                "previous_issues_closed": previous_issues_closed,
                "issue_close_change": round(issue_change, 4),
                "net_issue_flow": issue_balance,
                "releases": releases,
                "commits_per_week": round(commits * 7 / window_days, 1),
                "releases_per_month": round(releases * 30 / window_days, 1),
            },
            "responsiveness": {
                "median_issue_close_hours": round(median(issue_hours), 1) if issue_hours else None,
                "median_pr_merge_hours": round(median(merge_hours), 1) if merge_hours else None,
                "pr_merge_rate": round(merge_rate, 4) if resolved_prs else None,
                "issue_close_rate": round(min(issues_closed / issues_opened, 2), 4)
                if issues_opened
                else None,
                "merged_pr_sample_size": len(merged),
                "resolved_pr_sample_size": len(resolved_prs),
                "closed_issue_sample_size": len(closed_issues),
            },
            "community": {
                "active_contributors": active,
                "contributors_observed": len(cumulative_contributions),
                "resilience_score": round(100 - concentration["risk_score"], 1),
            },
            "freshness": {
                "last_commit_at": last_commit_at.isoformat() if last_commit_at else None,
                "last_release_at": last_release_at.isoformat() if last_release_at else None,
                "days_since_commit": days_since_commit,
                "days_since_release": days_since_release,
            },
            "growth": {
                "star_rate": round(star_growth, 4),
                "contributor_rate": round(contributor_growth, 4),
                "history_available": older is not None,
            },
            "assessment": {"status": status, "tone": status_tone},
            "data_quality": {
                "confidence_score": round(confidence_score, 1),
                "snapshot_count": len(snapshots),
                "snapshot_span_days": round(snapshot_span_days, 1),
                "event_count": evidence_events,
            },
        },
    )
    session.add(metric)
    await session.commit()
    return metric
