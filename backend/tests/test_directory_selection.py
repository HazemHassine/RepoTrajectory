import pytest
from datetime import datetime, timezone, timedelta
from app.db.models import CatalogRepository
from app.services.directory import reconcile_directory_and_cohort
from app.core.config import Settings

@pytest.mark.asyncio
async def test_diversity_cap_enforcement(db_session):
    """
    Test that directory selection strictly enforces the 25% maximum language diversity cap.
    """
    now = datetime.now(timezone.utc)
    repos = []
    
    # 60 Python (all high scores)
    for i in range(60):
        repos.append(CatalogRepository(
            github_id=1000 + i,
            owner="python-org",
            name=f"py-repo-{i}",
            full_name=f"python-org/py-repo-{i}",
            primary_language="Python",
            stars=10000 - i * 10,
            forks=500,
            pushed_at=now - timedelta(days=1),
            created_at=now - timedelta(days=200),
            updated_at=now - timedelta(days=1),
            last_discovered_at=now,
            last_observed_at=now,
            selection_score=95.0 - (i * 0.1),
            is_fork=False,
            archived=False,
            classification="library"
        ))
        
    # 10 each for Rust, Go, TypeScript, Java
    for lang, base_id, base_score in [
        ("Rust", 2000, 80.0),
        ("Go", 3000, 75.0),
        ("TypeScript", 4000, 70.0),
        ("Java", 5000, 65.0)
    ]:
        for i in range(10):
            repos.append(CatalogRepository(
                github_id=base_id + i,
                owner=f"{lang.lower()}-org",
                name=f"{lang.lower()}-repo-{i}",
                full_name=f"{lang.lower()}-org/{lang.lower()}-repo-{i}",
                primary_language=lang,
                stars=5000 - i * 10,
                forks=200,
                pushed_at=now - timedelta(days=2),
                created_at=now - timedelta(days=300),
                updated_at=now - timedelta(days=2),
                last_discovered_at=now,
                last_observed_at=now,
                selection_score=base_score - (i * 0.1),
                is_fork=False,
                archived=False,
                classification="library"
            ))
            
    db_session.add_all(repos)
    await db_session.commit()
    
    custom_settings = Settings(
        _env_file=None,
        directory_limit=40,
        directory_language_cap=0.25,
        deep_cohort_limit=10
    )
    
    result = await reconcile_directory_and_cohort(
        db_session,
        settings=custom_settings
    )
    
    assert result["directory_count"] == 40
    
    # Verify in DB:
    from sqlalchemy import select, func
    res = await db_session.execute(
        select(CatalogRepository.primary_language, func.count(CatalogRepository.github_id))
        .where(CatalogRepository.is_directory.is_(True))
        .group_by(CatalogRepository.primary_language)
    )
    counts = dict(res.all())
    
    # Max allowed per language is int(40 * 0.25) = 10
    assert counts.get("Python", 0) <= 10
    assert counts.get("Rust", 0) <= 10
    assert counts.get("Go", 0) <= 10
    assert counts.get("TypeScript", 0) <= 10
    assert counts.get("Java", 0) <= 10

@pytest.mark.asyncio
async def test_deep_cohort_selection(db_session):
    """
    Test that exactly deep_cohort_limit repositories are flagged as is_deep=True among top selection scores.
    """
    now = datetime.now(timezone.utc)
    for i in range(25):
        db_session.add(CatalogRepository(
            github_id=9000 + i,
            owner="deep-org",
            name=f"deep-repo-{i}",
            full_name=f"deep-org/deep-repo-{i}",
            primary_language=f"Lang{i % 4}",
            stars=1000 + i,
            forks=100,
            pushed_at=now,
            created_at=now - timedelta(days=100),
            updated_at=now,
            last_discovered_at=now,
            last_observed_at=now,
            selection_score=float(i + 10),
            is_fork=False,
            archived=False,
            classification="developer_tool"
        ))
    await db_session.commit()
    
    custom_settings = Settings(
        _env_file=None,
        directory_limit=20,
        directory_language_cap=0.30,
        deep_cohort_limit=5
    )
    
    result = await reconcile_directory_and_cohort(
        db_session,
        settings=custom_settings
    )
    
    assert result["deep_cohort_count"] == 5
    
    from sqlalchemy import select, func
    res = await db_session.execute(
        select(func.count(CatalogRepository.github_id))
        .where(CatalogRepository.is_deep.is_(True))
    )
    deep_count = res.scalar_one()
    assert deep_count == 5

@pytest.mark.asyncio
async def test_candidate_pruning(db_session):
    """
    Test candidate pool bounds: removes candidates beyond capacity or older than retention days.
    """
    now = datetime.now(timezone.utc)
    # Add 5 active high-scoring repos across 5 languages to fill directory of 5
    for idx, lang in enumerate(["Go", "Rust", "TypeScript", "Java", "Ruby"]):
        db_session.add(CatalogRepository(
            github_id=7000 + idx,
            owner=f"{lang.lower()}-org",
            name=f"active-{lang.lower()}",
            full_name=f"{lang.lower()}-org/active-{lang.lower()}",
            primary_language=lang,
            stars=5000,
            forks=200,
            pushed_at=now,
            created_at=now - timedelta(days=100),
            updated_at=now,
            last_discovered_at=now,
            last_observed_at=now,
            selection_score=90.0,
            is_fork=False,
            archived=False,
            classification="developer_tool"
        ))

    # Add old candidate in catalog (stale, low score, not selected into directory of 5)
    db_session.add(CatalogRepository(
        github_id=8888,
        owner="old-org",
        name="old-repo",
        full_name="old-org/old-repo",
        primary_language="Python",
        stars=10,
        forks=1,
        pushed_at=now - timedelta(days=120),
        created_at=now - timedelta(days=400),
        updated_at=now - timedelta(days=100),
        last_discovered_at=now - timedelta(days=95),
        last_observed_at=now - timedelta(days=95),
        selection_score=5.0,
        is_fork=False,
        archived=False,
        is_directory=False,
        is_deep=False,
        tier="candidate",
        classification="library"
    ))
    await db_session.commit()
    
    custom_settings = Settings(
        _env_file=None,
        directory_limit=5,
        directory_language_cap=0.25,
        candidate_pool_limit=10,
        candidate_retention_days=90
    )
    result = await reconcile_directory_and_cohort(
        db_session,
        settings=custom_settings
    )
    assert result["pruned_candidates"] >= 1
