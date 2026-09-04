import pytest
from datetime import datetime, timezone, timedelta
from app.db.models import CatalogRepository, RepositorySearchDocument, QueryEmbeddingCache
from app.services.search import (
    hybrid_search,
    get_or_create_query_embedding,
    encode_cursor,
    decode_cursor
)
from app.services.ai.fallback_provider import FallbackAIProvider
from app.core.config import get_settings

@pytest.mark.asyncio
async def test_reciprocal_rank_fusion(db_session):
    """
    Test that search combines lexical matching and vector similarity using RRF (k=60).
    """
    now = datetime.now(timezone.utc)
    
    r1 = CatalogRepository(
        github_id=8001,
        owner="ml-org",
        name="vector-database",
        full_name="ml-org/vector-database",
        description="Fast distributed vector database with pgvector and similarity search",
        primary_language="Rust",
        stars=1500,
        forks=80,
        created_at=now - timedelta(days=100),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="database"
    )
    r2 = CatalogRepository(
        github_id=8002,
        owner="ml-org",
        name="tensor-engine",
        full_name="ml-org/tensor-engine",
        description="Tensor operations engine supporting vector indices",
        primary_language="C++",
        stars=800,
        forks=40,
        created_at=now - timedelta(days=100),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="library"
    )
    r3 = CatalogRepository(
        github_id=8003,
        owner="web-org",
        name="blog-frontend",
        full_name="web-org/blog-frontend",
        description="Simple markdown blogging platform",
        primary_language="TypeScript",
        stars=100,
        forks=5,
        created_at=now - timedelta(days=100),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="framework"
    )
    db_session.add_all([r1, r2, r3])
    await db_session.commit()
    
    # Add search documents
    d1 = RepositorySearchDocument(
        github_id=r1.github_id,
        name=r1.name,
        owner=r1.owner,
        full_name=r1.full_name,
        description=r1.description,
        topics_text="vector database similarity search",
        readme_text="Fast distributed vector database with pgvector and similarity search",
        updated_at=now
    )
    d2 = RepositorySearchDocument(
        github_id=r2.github_id,
        name=r2.name,
        owner=r2.owner,
        full_name=r2.full_name,
        description=r2.description,
        topics_text="tensor vector",
        readme_text="Tensor operations engine supporting vector indices",
        updated_at=now
    )
    d3 = RepositorySearchDocument(
        github_id=r3.github_id,
        name=r3.name,
        owner=r3.owner,
        full_name=r3.full_name,
        description=r3.description,
        topics_text="blog markdown",
        readme_text="Simple markdown blogging platform",
        updated_at=now
    )
    db_session.add_all([d1, d2, d3])
    await db_session.commit()
    
    ai_provider = FallbackAIProvider()
    
    results = await hybrid_search(
        db_session,
        query="vector database",
        ai_provider=ai_provider,
        limit=10
    )
    
    assert results["total_count"] >= 1
    items = results["items"]
    top_repo = items[0]
    assert top_repo["name"] == "vector-database"

@pytest.mark.asyncio
async def test_lexical_fallback_when_ai_offline(db_session):
    """
    Test that when AI provider is None (offline/degraded), search falls back cleanly
    to lexical search without crashing.
    """
    now = datetime.now(timezone.utc)
    r = CatalogRepository(
        github_id=8004,
        owner="offline-org",
        name="resilient-search",
        full_name="offline-org/resilient-search",
        description="A resilient search library with zero dependencies",
        primary_language="Python",
        stars=500,
        forks=20,
        created_at=now - timedelta(days=100),
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        is_directory=True,
        is_fork=False,
        archived=False,
        classification="library"
    )
    db_session.add(r)
    await db_session.commit()
    
    db_session.add(RepositorySearchDocument(
        github_id=r.github_id,
        name=r.name,
        owner=r.owner,
        full_name=r.full_name,
        description=r.description,
        topics_text="search resilient",
        readme_text="resilient search",
        updated_at=now
    ))
    await db_session.commit()
    
    results = await hybrid_search(
        db_session,
        query="resilient search",
        ai_provider=None,
        limit=5
    )
    
    assert results["total_count"] >= 1
    assert results["items"][0]["name"] == "resilient-search"

@pytest.mark.asyncio
async def test_query_embedding_caching(db_session):
    """
    Test query embedding cache lookup and storage via get_or_create_query_embedding.
    """
    query = "scalable distributed consensus"
    ai_provider = FallbackAIProvider()
    settings = get_settings()
    
    emb1 = await get_or_create_query_embedding(db_session, query=query, ai_provider=ai_provider, settings=settings)
    assert emb1 is not None
    assert len(emb1) == 1536
    
    # Second call should fetch from cache
    emb2 = await get_or_create_query_embedding(db_session, query=query, ai_provider=ai_provider, settings=settings)
    assert emb1 == emb2
