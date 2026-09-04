import pytest
from datetime import datetime, timezone, timedelta
from app.db.models import CatalogRepository, ScoutAssessment, RepositorySearchDocument

@pytest.mark.asyncio
async def test_api_v2_repositories_cursor_pagination(client, db_session):
    """
    Test GET /api/v2/repositories returns cursor-based pagination and lenses.
    """
    now = datetime.now(timezone.utc)
    for i in range(15):
        db_session.add(CatalogRepository(
            github_id=20000 + i,
            owner="cursor-org",
            name=f"repo-{i:02d}",
            full_name=f"cursor-org/repo-{i:02d}",
            description=f"Description for repo {i}",
            primary_language="TypeScript" if i % 2 == 0 else "Rust",
            stars=1000 - i * 10,
            forks=50,
            created_at=now - timedelta(days=100),
            updated_at=now,
            last_discovered_at=now,
            last_observed_at=now,
            is_directory=True,
            is_fork=False,
            archived=False,
            selection_score=80.0 - i,
            classification="developer_tool"
        ))
    await db_session.commit()

    # Page 1: limit 5
    res = await client.get("/api/v2/repositories?limit=5&lens=developer")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 5
    assert data["total_count"] == 15
    assert data["next_cursor"] is not None
    assert data["lens"] == "developer"
    first_item = data["items"][0]
    assert "github_id" in first_item
    assert "lens_metrics" in first_item

    # Page 2 using cursor
    cursor = data["next_cursor"]
    res2 = await client.get(f"/api/v2/repositories?limit=5&cursor={cursor}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 5
    assert data2["items"][0]["github_id"] != first_item["github_id"]

@pytest.mark.asyncio
async def test_api_v2_unified_profile(client, db_session):
    """
    Test GET /api/v2/repositories/{owner}/{repo} returns 5-section unified profile.
    """
    now = datetime.now(timezone.utc)
    repo = CatalogRepository(
        github_id=30001,
        owner="unify-org",
        name="profile-target",
        full_name="unify-org/profile-target",
        description="Unified profile target repo",
        primary_language="Python",
        stars=3500,
        forks=220,
        created_at=now - timedelta(days=150),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_deep=True,
        is_fork=False,
        archived=False,
        classification="library",
        readme_excerpt="This is a verified library for distributed systems."
    )
    db_session.add(repo)
    
    # Add scout card
    db_session.add(ScoutAssessment(
        github_id=repo.github_id,
        version=1,
        promise_score=84.5,
        quantitative_score=86.0,
        ai_score=81.0,
        confidence=0.88,
        rationale="Strong adoption and delivery velocity",
        why_it_surfaced="High commit cadence and rapid release iterations.",
        supporting_facts=["Fast issue resolution", "Zero known vulnerabilities"],
        risk_flags=[],
        score_components={},
        model_identity="gpt-4o-mini",
        created_at=now,
        expires_at=now + timedelta(days=7),
        is_current=True
    ))
    await db_session.commit()

    res = await client.get("/api/v2/repositories/unify-org/profile-target")
    assert res.status_code == 200
    data = res.json()
    
    # Section 1: Overview & Project Purpose
    assert data["catalog"]["full_name"] == "unify-org/profile-target"
    assert data["readme_excerpt"] == "This is a verified library for distributed systems."
    
    # Section 4: Scout & Investor momentum
    assert data["scout"] is not None
    assert data["scout"]["promise_score"] == 84.5
    assert data["scout"]["model_identity"] == "gpt-4o-mini"
    
    # Section 5: Provenance
    assert "provenance" in data

@pytest.mark.asyncio
async def test_api_v2_scout_feed(client, db_session):
    """
    Test GET /api/v2/scout returns high-promise discoveries.
    """
    now = datetime.now(timezone.utc)
    repo = CatalogRepository(
        github_id=40001,
        owner="scout-hacker",
        name="early-gem",
        full_name="scout-hacker/early-gem",
        description="Early gem compiler",
        primary_language="Rust",
        stars=12,
        forks=3,
        created_at=now - timedelta(days=40),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        scout_eligible=True,
        promise_score=78.0,
        classification="developer_tool"
    )
    db_session.add(repo)
    db_session.add(ScoutAssessment(
        github_id=repo.github_id,
        version=1,
        promise_score=78.0,
        quantitative_score=80.0,
        ai_score=73.3,
        confidence=0.82,
        rationale="Early stage breakout",
        why_it_surfaced="High commit volume relative to star count",
        supporting_facts=["Daily commit cadence"],
        risk_flags=[],
        model_identity="fallback",
        created_at=now,
        expires_at=now + timedelta(days=7),
        is_current=True
    ))
    await db_session.commit()

    res = await client.get("/api/v2/scout?min_promise_score=60")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert item["full_name"] == "scout-hacker/early-gem"
    assert item["promise_score"] == 78.0
    assert "why_it_surfaced" in item
    assert len(item["supporting_facts"]) > 0

@pytest.mark.asyncio
async def test_api_v2_facets(client, db_session):
    """
    Test GET /api/v2/facets returns directory statistics.
    """
    now = datetime.now(timezone.utc)
    db_session.add(CatalogRepository(
        github_id=50001,
        owner="facet-org",
        name="facet-repo",
        full_name="facet-org/facet-repo",
        primary_language="Python",
        stars=100,
        forks=10,
        created_at=now,
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="library"
    ))
    await db_session.commit()

    res = await client.get("/api/v2/facets")
    assert res.status_code == 200
    data = res.json()
    assert "languages" in data
    assert "categories" in data
    assert "evidence_levels" in data
    assert any(l["name"] == "Python" for l in data["languages"])

@pytest.mark.asyncio
async def test_api_v2_health_degraded_status(client):
    """
    Test GET /api/v2/health returns service status and degraded flag when appropriate.
    """
    res = await client.get("/api/v2/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "ai_service" in data
    assert "directory_count" in data
    assert "degraded_features" in data
