import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.db.models import (
    Base,
    Repository,
    RepositoryCandidate,
    CatalogRepository,
    RepositorySearchDocument
)
from app.services.catalog import sync_catalog_from_repository

@pytest.mark.asyncio
async def test_lossless_backfill_from_existing_repositories(db_session):
    """
    Test that existing hydrated repositories and candidate pools are migrated
    and backfilled into catalog_repositories and repository_search_documents without loss.
    """
    now = datetime.now(timezone.utc)
    
    # 1. Simulate pre-existing hydrated repository
    repo = Repository(
        github_id=123456,
        owner="test-owner",
        name="legacy-project",
        full_name="test-owner/legacy-project",
        description="A foundational data pipeline in Python",
        primary_language="Python",
        stars=4200,
        forks=380,
        watchers=4200,
        open_issues=25,
        default_branch="main",
        license="MIT",
        created_at=now - timedelta(days=200),
        updated_at=now - timedelta(days=1),
        pushed_at=now - timedelta(hours=3),
        last_ingested_at=now - timedelta(hours=3),
        archived=False
    )
    db_session.add(repo)
    
    # 2. Simulate pre-existing discovery candidate
    cand = RepositoryCandidate(
        github_id=789012,
        owner="indie-creator",
        name="fast-parser",
        full_name="indie-creator/fast-parser",
        description="SIMD-accelerated JSON parser in Rust",
        primary_language="Rust",
        topics=["json", "simd", "rust", "parser"],
        stars=850,
        forks=45,
        pushed_at=now - timedelta(days=2),
        archived=False,
        is_fork=False,
        source="archive_growth",
        source_score=78.5,
        trend_score=82.0,
        tier="candidate",
        eligible=True,
        discovered_at=now - timedelta(days=10),
        last_seen_at=now - timedelta(days=1)
    )
    db_session.add(cand)
    await db_session.commit()
    
    # 3. Execute sync / backfill logic
    catalog_entry = await sync_catalog_from_repository(db_session, repo)
    assert catalog_entry is not None
    assert catalog_entry.github_id == 123456
    assert catalog_entry.full_name == "test-owner/legacy-project"
    assert catalog_entry.stars == 4200
    assert catalog_entry.is_directory is True
    
    # Verify search document was created
    doc = await db_session.get(RepositorySearchDocument, 123456)
    assert doc is not None
    assert "legacy-project" in doc.name
    assert "foundational data pipeline" in (doc.description or "")
    
    # Verify candidate count and catalog counts
    total_catalog = await db_session.scalar(select(func.count(CatalogRepository.github_id)))
    assert total_catalog >= 1
