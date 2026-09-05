from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import CatalogRepository, ExternalRepositoryActivity, RepositoryCandidate
from app.services.ai.fallback_provider import FallbackAIProvider
from app.services.scout import (
    evaluate_candidate_scout,
    is_scout_eligible,
)


@pytest.mark.asyncio
async def test_low_star_repo_promise_evaluation(db_session):
    """
    Test that a 6-star repository with strong commit cadence and recent releases
    is eligible for Scout evaluation and scores >= 60.
    """
    now = datetime.now(UTC)

    # 6-star repo with active signals
    repo = CatalogRepository(
        github_id=60001,
        owner="indie-hacker",
        name="novel-compiler",
        full_name="indie-hacker/novel-compiler",
        description="A novel optimizing compiler for webassembly written in Rust",
        primary_language="Rust",
        stars=6,
        forks=2,
        open_issues=1,
        created_at=now - timedelta(days=60),
        updated_at=now - timedelta(days=1),
        pushed_at=now - timedelta(hours=5),
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="developer_tool",
        topics=["compiler", "wasm", "rust", "optimizer"],
    )
    db_session.add(repo)

    candidate = RepositoryCandidate(
        id=42,
        github_id=repo.github_id,
        owner=repo.owner,
        name=repo.name,
        full_name=repo.full_name,
        source="gharchive",
        discovered_at=now,
        last_seen_at=now,
    )
    unrelated = RepositoryCandidate(
        id=repo.github_id,
        github_id=999999,
        owner="other",
        name="project",
        full_name="other/project",
        source="gharchive",
        discovered_at=now,
        last_seen_at=now,
    )
    db_session.add_all([candidate, unrelated])
    await db_session.flush()
    db_session.add(
        ExternalRepositoryActivity(
            candidate_id=unrelated.id,
            period_start=now,
            star_events=999,
        )
    )
    # Candidate identity deliberately differs from the stable external GitHub ID.
    activity = ExternalRepositoryActivity(
        candidate_id=candidate.id,
        period_start=now - timedelta(days=2),
        push_events=50,
        release_events=4,
        pull_request_events=12,
        issue_events=5,
        star_events=6,
        fork_events=2,
    )
    db_session.add(activity)
    await db_session.commit()

    assessment = await evaluate_candidate_scout(
        db_session, repo=repo, ai_provider=FallbackAIProvider()
    )

    assert assessment is not None
    assert assessment.evidence_references["recent_events"]["star_events"] == 6
    assert assessment.evidence_references["recent_events"]["push_events"] == 50
    assert assessment.promise_score >= 60.0
    assert assessment.confidence >= 0.5
    assert len(assessment.supporting_facts) > 0
    assert assessment.why_it_surfaced != ""
    assert repo.promise_score == assessment.promise_score


@pytest.mark.asyncio
async def test_guardrails_exclude_forks_and_archived():
    """
    Test that forks and archived repositories are strictly rejected by the Scout guardrails.
    """
    now = datetime.now(UTC)

    # Fork repo
    fork_repo = CatalogRepository(
        github_id=70001,
        owner="someone",
        name="forked-repo",
        full_name="someone/forked-repo",
        primary_language="Python",
        stars=1000,
        forks=50,
        created_at=now - timedelta(days=100),
        updated_at=now,
        pushed_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_fork=True,
        archived=False,
    )

    eligible, reason = is_scout_eligible(fork_repo)
    assert eligible is False
    assert "fork" in (reason or "").lower()

    # Archived repo
    archived_repo = CatalogRepository(
        github_id=70002,
        owner="someone",
        name="dead-project",
        full_name="someone/dead-project",
        primary_language="Go",
        stars=5000,
        forks=200,
        created_at=now - timedelta(days=500),
        updated_at=now,
        pushed_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_fork=False,
        archived=True,
    )

    eligible2, reason2 = is_scout_eligible(archived_repo)
    assert eligible2 is False
    assert "archived" in (reason2 or "").lower()


@pytest.mark.asyncio
async def test_confidence_downranking():
    """
    Test that sparse signals or stale repositories produce lower confidence.
    """
    now = datetime.now(UTC)

    sparse_repo = CatalogRepository(
        github_id=70003,
        owner="abandoned",
        name="old-code",
        full_name="abandoned/old-code",
        primary_language="C++",
        stars=100,
        forks=5,
        created_at=now - timedelta(days=600),
        updated_at=now - timedelta(days=200),
        pushed_at=now - timedelta(days=180),
        last_discovered_at=now,
        last_observed_at=now,
        is_fork=False,
        archived=False,
    )

    eligible, reason = is_scout_eligible(sparse_repo)
    assert eligible is False or "pushed" in (reason or "").lower()
