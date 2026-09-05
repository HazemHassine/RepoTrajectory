import math
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    CatalogRepository,
    ExternalRepositoryActivity,
    Issue,
    PullRequest,
    RepositoryCandidate,
    ScoutAssessment,
)
from app.services.ai import AIProvider, get_ai_provider

log = structlog.get_logger()

SOFTWARE_CLASSIFICATIONS = {"library", "framework", "developer_tool", "software"}


def is_scout_eligible(repo: CatalogRepository) -> tuple[bool, str | None]:
    """Check guardrails: exclude forks, archived repos, resource lists, and inactive projects.

    Has NO minimum star count.
    """
    if repo.is_fork:
        return False, "Excluded: repository is a fork"
    if repo.archived:
        return False, "Excluded: repository is archived"
    if (
        repo.classification
        and repo.classification not in SOFTWARE_CLASSIFICATIONS
        and repo.classification != "unclassified"
    ):
        return False, f"Excluded: non-software classification ({repo.classification})"
    if repo.pushed_at:
        age_days = (datetime.now(UTC) - repo.pushed_at).total_seconds() / 86400
        if age_days > 180:
            return False, f"Excluded: inactive for {int(age_days)} days (>180d threshold)"
    return True, None


def calculate_quantitative_scout_score(
    repo: CatalogRepository,
    activity_facts: dict[str, Any] | None = None,
) -> tuple[float, float, dict[str, Any]]:
    """Compute quantitative Scout score (0-100) and confidence (0-1).

    Evaluates:
      1. Adoption acceleration (stars, velocity, watchers)
      2. Development cadence (push freshness, push events, commits)
      3. Contributor breadth (contributors, forks)
      4. Release cadence (recent releases)
      5. Maintenance responsiveness (issues closed, PRs merged)
      6. Freshness (pushed_at recency)
      7. Evidence quality (description, topics, license, readme)
    """
    facts = activity_facts or {}
    now = datetime.now(UTC)

    # 1. Freshness (0-100)
    freshness = 0.0
    if repo.pushed_at:
        days_since_push = max(0.0, (now - repo.pushed_at).total_seconds() / 86400)
        freshness = max(0.0, 100.0 - (days_since_push * 1.5))
    else:
        freshness = 20.0

    # 2. Development cadence (0-100)
    push_events = facts.get("push_events", 0)
    pr_events = facts.get("pull_request_events", 0)
    cadence = min(100.0, 30.0 + (push_events * 3.0) + (pr_events * 5.0))

    # 3. Adoption acceleration (0-100)
    star_events = facts.get("star_events", 0)
    fork_events = facts.get("fork_events", 0)
    stars = repo.stars or 0
    # Reward relative momentum: even a 6-star project gaining 3 stars this week is accelerating!
    velocity_boost = star_events * 15.0 + fork_events * 10.0
    star_log = min(40.0, math.log1p(stars) * 6.0)
    adoption = min(100.0, 20.0 + velocity_boost + star_log)

    # 4. Contributor breadth & collaboration (0-100)
    forks = repo.forks or 0
    issue_events = facts.get("issue_events", 0)
    breadth = min(100.0, 25.0 + (forks * 8.0) + (pr_events * 4.0) + (issue_events * 2.0))

    # 5. Release activity (0-100)
    release_events = facts.get("release_events", 0)
    release_score = min(100.0, 20.0 + (release_events * 35.0))

    # 6. Maintenance responsiveness (0-100)
    # Closed issues or merged PRs vs open
    maintenance = 50.0
    if facts.get("merged_prs", 0) > 0 or facts.get("closed_issues", 0) > 0:
        maintenance = min(100.0, 60.0 + facts.get("merged_prs", 0) * 10.0)

    # 7. Evidence completeness & quality (0-100)
    evidence_points = 0.0
    if repo.description and len(repo.description) > 20:
        evidence_points += 25.0
    if repo.primary_language:
        evidence_points += 20.0
    if repo.license:
        evidence_points += 25.0
    if repo.topics and len(repo.topics) >= 2:
        evidence_points += 20.0
    if repo.readme_excerpt and len(repo.readme_excerpt) > 50:
        evidence_points += 10.0
    evidence_quality = min(100.0, evidence_points)

    # Composite quantitative score
    weighted_score = (
        0.25 * adoption
        + 0.20 * cadence
        + 0.15 * freshness
        + 0.15 * breadth
        + 0.10 * release_score
        + 0.15 * maintenance
    )
    quantitative_score = round(min(100.0, max(0.0, weighted_score)), 2)

    # Evidence Confidence (0.0 to 1.0)
    # Separate from score: penalize lack of signals rather than assuming neutral
    confidence_signals = 0.0
    if repo.description:
        confidence_signals += 0.2
    if repo.primary_language:
        confidence_signals += 0.15
    if repo.license:
        confidence_signals += 0.15
    if len(repo.topics or []) >= 2:
        confidence_signals += 0.15
    if (facts.get("total_events", 0) or 0) > 0:
        confidence_signals += 0.2
    if stars >= 5:
        confidence_signals += 0.15
    confidence = round(min(1.0, max(0.2, confidence_signals)), 2)

    components = {
        "adoption_acceleration": round(adoption, 1),
        "development_cadence": round(cadence, 1),
        "freshness": round(freshness, 1),
        "contributor_breadth": round(breadth, 1),
        "release_activity": round(release_score, 1),
        "maintenance_responsiveness": round(maintenance, 1),
        "evidence_quality": round(evidence_quality, 1),
    }

    return quantitative_score, confidence, components


async def evaluate_candidate_scout(
    session: AsyncSession,
    repo: CatalogRepository,
    ai_provider: AIProvider | None = None,
    settings: Settings | None = None,
) -> ScoutAssessment:
    """Run full Scout evaluation on one repository: 70% quantitative evidence + 30% structured AI."""
    cfg = settings or get_settings()
    provider = ai_provider or get_ai_provider(cfg)

    eligible, rejection = is_scout_eligible(repo)
    if not eligible:
        repo.scout_eligible = False
        repo.rejection_reason = rejection
        assessment = ScoutAssessment(
            github_id=repo.github_id,
            version=1,
            promise_score=0.0,
            quantitative_score=0.0,
            ai_score=0.0,
            confidence=0.0,
            rationale=rejection or "Ineligible for Scout",
            why_it_surfaced="Excluded by Scout guardrails.",
            supporting_facts=[],
            risk_flags=[rejection or "Ineligible"],
            score_components={},
            evidence_references={},
            model_identity="guardrails",
            prompt_version="v1",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            is_current=True,
        )
        session.add(assessment)
        await session.commit()
        return assessment

    # Gather recent external activity facts if any
    recent_cutoff = datetime.now(UTC) - timedelta(days=30)
    activity_row = (
        await session.execute(
            select(
                func.sum(ExternalRepositoryActivity.star_events).label("star_events"),
                func.sum(ExternalRepositoryActivity.fork_events).label("fork_events"),
                func.sum(ExternalRepositoryActivity.push_events).label("push_events"),
                func.sum(ExternalRepositoryActivity.pull_request_events).label(
                    "pull_request_events"
                ),
                func.sum(ExternalRepositoryActivity.issue_events).label("issue_events"),
                func.sum(ExternalRepositoryActivity.release_events).label("release_events"),
            )
            .join(
                RepositoryCandidate,
                RepositoryCandidate.id == ExternalRepositoryActivity.candidate_id,
            )
            .where(
                RepositoryCandidate.github_id == repo.github_id,
                ExternalRepositoryActivity.period_start >= recent_cutoff,
            )
        )
    ).first()

    facts: dict[str, Any] = {}
    if activity_row:
        facts = {
            "star_events": int(activity_row.star_events or 0),
            "fork_events": int(activity_row.fork_events or 0),
            "push_events": int(activity_row.push_events or 0),
            "pull_request_events": int(activity_row.pull_request_events or 0),
            "issue_events": int(activity_row.issue_events or 0),
            "release_events": int(activity_row.release_events or 0),
            "total_events": sum(
                int(getattr(activity_row, col) or 0)
                for col in (
                    "star_events",
                    "fork_events",
                    "push_events",
                    "pull_request_events",
                    "issue_events",
                    "release_events",
                )
            ),
        }

    # If linked to hydrated deep repo, gather deep facts
    if repo.repository_id:
        merged_prs = await session.scalar(
            select(func.count())
            .select_from(PullRequest)
            .where(
                PullRequest.repository_id == repo.repository_id,
                PullRequest.merged_at >= recent_cutoff,
            )
        )
        closed_issues = await session.scalar(
            select(func.count())
            .select_from(Issue)
            .where(Issue.repository_id == repo.repository_id, Issue.closed_at >= recent_cutoff)
        )
        facts["merged_prs"] = int(merged_prs or 0)
        facts["closed_issues"] = int(closed_issues or 0)

    # 1. Quantitative Score (0-100) & Confidence (0-1)
    quant_score, confidence, quant_components = calculate_quantitative_scout_score(repo, facts)

    # 2. Structured AI Evaluation (30%)
    candidate_data = {
        "source_url": f"https://github.com/{repo.full_name}",
        "full_name": repo.full_name,
        "description": repo.description,
        "primary_language": repo.primary_language,
        "topics": repo.topics or [],
        "stars": repo.stars,
        "forks": repo.forks,
        "open_issues": repo.open_issues,
        "license": repo.license,
        "classification": repo.classification,
        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        "default_branch": repo.default_branch,
        "recent_events": facts,
    }
    ai_eval = await provider.evaluate_scout(candidate_data)

    # 3. Composite Promise Score
    # 70% quantitative evidence + 30% structured AI evaluation
    promise_score = round((0.70 * quant_score) + (0.30 * ai_eval.overall_score), 1)

    now = datetime.now(UTC)
    expires = now + timedelta(days=7)

    # Demote existing current assessments for this repo
    await session.execute(
        update(ScoutAssessment)
        .where(ScoutAssessment.github_id == repo.github_id, ScoutAssessment.is_current.is_(True))
        .values(is_current=False)
    )

    assessment = ScoutAssessment(
        github_id=repo.github_id,
        version=1,
        promise_score=promise_score,
        quantitative_score=quant_score,
        ai_score=ai_eval.overall_score,
        confidence=confidence,
        rationale=f"Quantitative: {quant_score}/100, AI: {ai_eval.overall_score}/100",
        why_it_surfaced=(
            f"Observed {facts.get('total_events', 0)} compact GitHub public events "
            "in the last 30 days. Inspect releases and documentation for changes that matter."
            if ai_eval.model_identity.startswith("heuristic-") and facts.get("total_events")
            else ai_eval.why_it_surfaced
        ),
        supporting_facts=ai_eval.supporting_facts,
        uncertainty=ai_eval.uncertainty,
        risk_flags=ai_eval.risk_flags,
        score_components={
            "quantitative": quant_components,
            "ai": ai_eval.score_breakdown,
            "weights": {"quantitative": 0.70, "ai": 0.30},
        },
        evidence_references={
            "stars": repo.stars,
            "forks": repo.forks,
            "language": repo.primary_language,
            "topics": repo.topics,
            "recent_events": facts,
        },
        model_identity=ai_eval.model_identity,
        prompt_version=ai_eval.prompt_version,
        created_at=now,
        expires_at=expires,
        is_current=True,
    )
    session.add(assessment)

    # Update CatalogRepository record
    repo.scout_eligible = True
    repo.promise_score = promise_score
    repo.selection_score = max(repo.selection_score, quant_score)

    await session.commit()
    log.info(
        "scout_evaluation_complete",
        repository=repo.full_name,
        promise_score=promise_score,
        quant=quant_score,
        ai=ai_eval.overall_score,
        confidence=confidence,
    )
    return assessment


async def run_daily_scout_batch(
    session: AsyncSession,
    limit: int = 100,
    settings: Settings | None = None,
) -> int:
    """Select top unevaluated or materially changed Scout candidates and evaluate them."""
    cfg = settings or get_settings()
    provider = get_ai_provider(cfg)

    # Find candidates that are eligible, have no current assessment or whose assessment has expired
    # Pre-order by quantitative signals: pushed_at, stars, activity
    stmt = (
        select(CatalogRepository)
        .outerjoin(
            ScoutAssessment,
            (ScoutAssessment.github_id == CatalogRepository.github_id)
            & (ScoutAssessment.is_current.is_(True)),
        )
        .where(
            CatalogRepository.is_fork.is_(False),
            CatalogRepository.archived.is_(False),
            (ScoutAssessment.id.is_(None)) | (ScoutAssessment.expires_at <= datetime.now(UTC)),
        )
        .order_by(
            CatalogRepository.pushed_at.desc().nullslast(),
            CatalogRepository.stars.desc(),
        )
        .limit(limit)
    )
    candidates = list((await session.scalars(stmt)).all())
    count = 0
    for repo in candidates:
        try:
            await evaluate_candidate_scout(session, repo, ai_provider=provider, settings=cfg)
            count += 1
        except Exception as exc:
            log.warning("scout_candidate_eval_failed", repo=repo.full_name, error=str(exc))
    return count
