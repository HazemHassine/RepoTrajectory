import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CatalogRepository
from app.services.topics import TAXONOMY, clear_topic_cache


def make_repo(
    github_id: int,
    name: str,
    topics: list[str],
    description: str,
    primary_language: str = "Python",
    stars: int = 100,
    selection_score: float = 50.0,
    pushed_at: datetime | None = None,
) -> CatalogRepository:
    now = datetime.now(UTC)
    return CatalogRepository(
        github_id=github_id,
        owner="test-org",
        name=name,
        full_name=f"test-org/{name}",
        description=description,
        primary_language=primary_language,
        stars=stars,
        selection_score=selection_score,
        pushed_at=pushed_at or now,
        created_at=now,
        updated_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        topics=topics,
        archived=False,
        is_fork=False,
    )


@pytest.mark.asyncio
async def test_taxonomy_hierarchy_and_legacy_slugs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()
    response = await client.get("/api/v2/topics")
    assert response.status_code == 200
    topics = response.json()
    assert isinstance(topics, list)
    assert len(topics) == len(TAXONOMY)

    # Verify parent categories
    parent_slugs = {
        "web",
        "backend-apis",
        "data-databases",
        "infrastructure-devops",
        "developer-tools",
        "security",
        "mobile-desktop",
        "ai-machine-learning",
    }
    parents = [t for t in topics if t["parent_slug"] is None]
    assert {p["slug"] for p in parents} == parent_slugs

    # Verify all 8 legacy slugs are preserved as children under ai-machine-learning
    legacy_slugs = {
        "agent-frameworks",
        "rag",
        "evaluation",
        "observability",
        "model-serving",
        "vector-search",
        "mcp-tooling",
        "ai-infrastructure",
    }
    for slug in legacy_slugs:
        item = next((t for t in topics if t["slug"] == slug), None)
        assert item is not None, f"Legacy slug {slug} missing from topics"
        assert item["parent_slug"] == "ai-machine-learning"

    # Unknown topic returns 404
    assert (await client.get("/api/v2/topics/unknown-topic-slug")).status_code == 404


@pytest.mark.asyncio
async def test_precise_matching_and_false_positive_avoidance(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()

    # Repo 1: Genuine RAG repo with topic 'rag'
    r1 = make_repo(
        github_id=101,
        name="real-rag",
        description="A fast retrieval augmented generation engine",
        primary_language="Python",
        stars=500,
        topics=["rag", "python"],
    )

    # Repo 2: False positive trap - contains 'storage' and 'courage', but is NOT a rag repo
    r2 = make_repo(
        github_id=102,
        name="cloud-storage",
        description="Encourage enterprise cloud storage solutions",
        primary_language="Go",
        stars=300,
        topics=["storage", "cloud"],
    )

    # Repo 3: False positive trap - contains 'therapeutic' in description, but is NOT an API repo
    r3 = make_repo(
        github_id=103,
        name="bio-informatics",
        description="Therapeutic protein modeling",
        primary_language="Rust",
        stars=200,
        topics=["biology"],
    )

    # Repo 4: Genuine agent framework with topic 'ai-agents'
    r4 = make_repo(
        github_id=104,
        name="auto-agent",
        description="Autonomous multi-agent system",
        primary_language="Python",
        stars=1000,
        topics=["ai-agents"],
    )

    db_session.add_all([r1, r2, r3, r4])
    await db_session.commit()

    # Check RAG topic: only r1 must match, r2 (storage/courage) must NOT match!
    rag_resp = await client.get("/api/v2/topics/rag")
    assert rag_resp.status_code == 200
    rag_data = rag_resp.json()
    rag_ids = [p["github_id"] for p in rag_data["projects"]]
    assert 101 in rag_ids
    assert 102 not in rag_ids
    assert rag_data["total_count"] == 1

    # Check agent-frameworks: r4 matches via 'ai-agents' alias
    agent_resp = await client.get("/api/v2/topics/agent-frameworks")
    assert agent_resp.status_code == 200
    agent_data = agent_resp.json()
    agent_ids = [p["github_id"] for p in agent_data["projects"]]
    assert 104 in agent_ids

    # Check api-frameworks: r3 (therapeutic) must NOT match!
    api_resp = await client.get("/api/v2/topics/api-frameworks")
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    api_ids = [p["github_id"] for p in api_data["projects"]]
    assert 103 not in api_ids


@pytest.mark.asyncio
async def test_parent_deduplicated_union_and_counts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()

    # Repo matching both frontend-frameworks ('react') and fullstack-frameworks ('nextjs')
    r1 = make_repo(
        github_id=201,
        name="next-app",
        description="Modern web app built with React and Next.js",
        primary_language="TypeScript",
        stars=1200,
        topics=["react", "nextjs"],
    )

    # Repo matching only ui-components ('tailwind')
    r2 = make_repo(
        github_id=202,
        name="ui-lib",
        description="Headless component library",
        primary_language="TypeScript",
        stars=800,
        topics=["tailwind", "component-library"],
    )

    db_session.add_all([r1, r2])
    await db_session.commit()

    # Query child 'frontend-frameworks'
    ff_resp = await client.get("/api/v2/topics/frontend-frameworks")
    assert ff_resp.status_code == 200
    ff_data = ff_resp.json()
    assert ff_data["total_count"] == 1
    assert [p["github_id"] for p in ff_data["projects"]] == [201]

    # Query child 'fullstack-frameworks'
    fs_resp = await client.get("/api/v2/topics/fullstack-frameworks")
    assert fs_resp.status_code == 200
    fs_data = fs_resp.json()
    assert fs_data["total_count"] == 1
    assert [p["github_id"] for p in fs_data["projects"]] == [201]

    # Query parent 'web': Must contain deduplicated union (201 and 202), exactly 2 projects!
    web_resp = await client.get("/api/v2/topics/web")
    assert web_resp.status_code == 200
    web_data = web_resp.json()
    assert web_data["total_count"] == 2
    web_ids = [p["github_id"] for p in web_data["projects"]]
    assert len(web_ids) == 2
    assert set(web_ids) == {201, 202}
    assert web_data["topic"]["repository_count"] == 2


@pytest.mark.asyncio
async def test_filters_languages_facets_and_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()

    r1 = make_repo(
        github_id=301,
        name="pg-tool",
        description="Postgres database client and migration manager",
        primary_language="Python",
        stars=600,
        topics=["postgres", "database"],
    )

    r2 = make_repo(
        github_id=302,
        name="sql-orm",
        description="High performance SQL ORM and query builder",
        primary_language="Rust",
        stars=1500,
        topics=["sql", "orm"],
    )

    r3 = make_repo(
        github_id=303,
        name="redis-cache",
        description="Distributed cache layer with Redis",
        primary_language="Go",
        stars=900,
        topics=["redis", "cache"],
    )

    db_session.add_all([r1, r2, r3])
    await db_session.commit()

    # Search within topic using `q=migration`
    q_resp = await client.get("/api/v2/topics/data-databases?q=migration")
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert q_data["total_count"] == 1
    assert q_data["projects"][0]["github_id"] == 301

    # Language facet check: language facets represent topic matches BEFORE language filter
    # Filter by language=Rust
    lang_resp = await client.get("/api/v2/topics/data-databases?language=Rust")
    assert lang_resp.status_code == 200
    lang_data = lang_resp.json()
    # total_count reflects filtered count (1 repo in Rust)
    assert lang_data["total_count"] == 1
    assert lang_data["projects"][0]["github_id"] == 302
    # But languages list shows all available languages before the filter!
    lang_facet_vals = {f["value"]: f["count"] for f in lang_data["languages"]}
    assert "Rust" in lang_facet_vals
    assert "Python" in lang_facet_vals
    assert "Go" in lang_facet_vals


@pytest.mark.asyncio
async def test_sorting_deterministic_ties_and_cursor_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()
    now = datetime.now(UTC)

    # 4 repos in developer-tools with ties in stars and selection scores
    repos = [
        make_repo(
            github_id=401,
            name="tool-b",
            description="Terminal command line runner B",
            primary_language="Go",
            stars=500,
            selection_score=75.0,
            pushed_at=now - timedelta(days=2),
            topics=["cli"],
        ),
        make_repo(
            github_id=402,
            name="tool-a",
            description="Terminal command line runner A",
            primary_language="Go",
            stars=500,  # Exact tie with 401
            selection_score=75.0,  # Exact tie with 401
            pushed_at=now - timedelta(days=2),
            topics=["cli"],
        ),
        make_repo(
            github_id=403,
            name="tool-c",
            description="Terminal command line runner C",
            primary_language="Go",
            stars=800,
            selection_score=85.0,
            pushed_at=now - timedelta(days=1),
            topics=["cli"],
        ),
        make_repo(
            github_id=404,
            name="tool-d",
            description="Terminal command line runner D",
            primary_language="Go",
            stars=200,
            selection_score=60.0,
            pushed_at=now - timedelta(days=5),
            topics=["cli"],
        ),
    ]
    db_session.add_all(repos)
    await db_session.commit()

    # Sort by stars: 403 (800) -> 401 & 402 tie (500) -> 404 (200)
    # Tie between 401 and 402 broken by github_id ASC -> 401 then 402
    page1 = await client.get("/api/v2/topics/cli-terminal?sort=stars&limit=2")
    assert page1.status_code == 200
    p1_data = page1.json()
    assert len(p1_data["projects"]) == 2
    assert p1_data["projects"][0]["github_id"] == 403
    assert p1_data["projects"][1]["github_id"] == 401
    assert p1_data["next_cursor"] is not None

    cursor = p1_data["next_cursor"]
    page2 = await client.get(f"/api/v2/topics/cli-terminal?sort=stars&limit=2&cursor={cursor}")
    assert page2.status_code == 200
    p2_data = page2.json()
    assert len(p2_data["projects"]) == 2
    assert p2_data["projects"][0]["github_id"] == 402
    assert p2_data["projects"][1]["github_id"] == 404
    assert p2_data["next_cursor"] is None  # End of pages


@pytest.mark.asyncio
async def test_cursor_validation_and_tampering(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()
    # 1. Invalid base64
    res = await client.get("/api/v2/topics/cli-terminal?cursor=not-valid-base64!@#$")
    assert res.status_code == 400

    # 2. Valid base64 but invalid JSON
    bad_json = base64.urlsafe_b64encode(b"not json").decode("utf-8")
    res = await client.get(f"/api/v2/topics/cli-terminal?cursor={bad_json}")
    assert res.status_code == 400

    # 3. Context mismatch: cursor generated for another topic
    mismatched_slug = base64.urlsafe_b64encode(
        json.dumps({"slug": "web", "q": "", "lang": "", "sort": "relevance", "offset": 10}).encode(
            "utf-8"
        )
    ).decode("utf-8")
    res = await client.get(f"/api/v2/topics/cli-terminal?cursor={mismatched_slug}")
    assert res.status_code == 400
    assert "Cursor context does not match" in res.json()["detail"]

    # 4. Context mismatch: cursor generated for sort=stars used with sort=updated
    mismatched_sort = base64.urlsafe_b64encode(
        json.dumps(
            {"slug": "cli-terminal", "q": "", "lang": "", "sort": "stars", "offset": 10}
        ).encode("utf-8")
    ).decode("utf-8")
    res = await client.get(f"/api/v2/topics/cli-terminal?sort=updated&cursor={mismatched_sort}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_public_reads_make_zero_external_requests(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clear_topic_cache()
    # Ensure with respx that any outbound HTTP request would raise an error
    with respx.mock(assert_all_called=False) as respx_mock:
        # If any external call happens, respx will record or block it
        topics_res = await client.get("/api/v2/topics")
        assert topics_res.status_code == 200

        detail_res = await client.get("/api/v2/topics/web")
        assert detail_res.status_code == 200

        # Assert no external calls were made
        assert respx_mock.calls.call_count == 0
