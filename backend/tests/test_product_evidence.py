from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import (
    CatalogRepository,
    ExternalEvidenceItem,
    RepositoryChangeEvent,
    RepositorySourceState,
)
from app.services.evidence import (
    changes_between,
    prune_evidence,
    record_failure,
    save_observation,
    verified_package,
)
from app.services.evidence_sources import (
    DepsDevAdapter,
    Evidence,
    HackerNewsAdapter,
    NpmAdapter,
    NpmDownloadsAdapter,
    Observation,
    OsvAdapter,
    PypiAdapter,
    PypiDownloadsAdapter,
    SourceHTTP,
    SourceUnavailable,
    github_name,
    package_targets,
)


def repository(gid=1, name="tool"):
    now = datetime.now(UTC)
    return CatalogRepository(
        github_id=gid,
        owner="org",
        name=name,
        full_name=f"org/{name}",
        description="A multi agent framework",
        primary_language="Python",
        license="MIT",
        created_at=now,
        updated_at=now,
        pushed_at=now,
        last_discovered_at=now,
        last_observed_at=now,
        topics=["multi-agent"],
    )


def test_explicit_package_targets_and_github_url_boundaries():
    assert package_targets("react uv ray langchain") == []
    assert package_targets(
        "https://www.npmjs.com/package/@org/tool https://pypi.org/project/tool/"
    ) == [
        ("npm", "@org/tool"),
        ("pypi", "tool"),
    ]
    assert github_name("https://github.com.evil.test/org/tool") is None
    assert github_name("git+https://github.com/Org/Tool.git") == "org/tool"


@pytest.mark.asyncio
async def test_numeric_identity_and_ambiguous_matching():
    github = AsyncMock()
    github.get_json.return_value = {"id": 123, "full_name": "renamed/tool"}
    assert await verified_package(github, 123, ["https://github.com/old/tool"]) == (
        "https://github.com/renamed/tool"
    )
    assert await verified_package(github, 456, ["https://github.com/old/tool"]) is None
    github.reset_mock()
    assert (
        await verified_package(
            github,
            123,
            [
                "https://github.com/a/tool",
                "https://github.com/b/tool",
            ],
        )
        is None
    )
    github.get_json.assert_not_called()


@pytest.mark.parametrize(
    ("adapter", "key", "payload", "expected"),
    [
        (
            NpmAdapter(),
            "tool",
            {"version": "1.0", "repository": {"url": "https://github.com/org/tool"}},
            "version",
        ),
        (
            PypiAdapter(),
            "tool",
            {"info": {"version": "1.0", "project_urls": {"Source": "https://github.com/org/tool"}}},
            "version",
        ),
        (
            NpmDownloadsAdapter(),
            "tool",
            {"downloads": 123, "start": "2026-01-01", "end": "2026-01-07"},
            "downloads",
        ),
        (PypiDownloadsAdapter(), "tool", {"data": {"last_week": 123}}, "downloads"),
        (DepsDevAdapter(), "npm:tool:1.0", {"licenses": ["MIT"]}, "licenses"),
        (OsvAdapter(), "npm:tool:1.0", {"vulns": []}, "checked"),
    ],
)
@pytest.mark.asyncio
async def test_adapters_normalize_mocked_http(adapter, key, payload, expected):
    with respx.mock:
        respx.route().respond(200, json=payload)
        async with httpx.AsyncClient() as http:
            observation = await adapter.collect(SourceHTTP(http), key)
    assert expected in observation.facts


@pytest.mark.asyncio
async def test_osv_fixed_versions_are_scoped_to_checked_package():
    payload = {
        "vulns": [
            {
                "id": "TEST-1",
                "summary": "Test advisory",
                "affected": [
                    {
                        "package": {"name": "tool", "ecosystem": "npm"},
                        "ranges": [{"events": [{"fixed": "1.1"}]}],
                    },
                    {
                        "package": {"name": "unrelated", "ecosystem": "npm"},
                        "ranges": [{"events": [{"fixed": "99"}]}],
                    },
                ],
            }
        ]
    }
    with respx.mock:
        route = respx.post("https://api.osv.dev/v1/query").respond(200, json=payload)
        async with httpx.AsyncClient() as http:
            result = await OsvAdapter().collect(SourceHTTP(http), "npm:tool:1.0")
        assert route.calls[0].request.content
    assert result.items[0].details["fixed_versions"] == ["1.1"]
    assert result.facts["finding_ids"] == ["TEST-1"]


@pytest.mark.asyncio
async def test_hn_rejects_name_only_hits_and_deduplicates_announcements():
    with respx.mock:
        respx.route().respond(
            200,
            json={
                "hits": [
                    {
                        "objectID": "1",
                        "title": "Show HN: Tool",
                        "url": "https://github.com/org/tool",
                    },
                    {"objectID": "2", "title": "Tool", "url": "https://github.com/other/tool"},
                    {"objectID": "3", "title": "Tool again", "url": "https://github.com/org/tool"},
                ]
            },
        )
        async with httpx.AsyncClient() as http:
            result = await HackerNewsAdapter().collect(SourceHTTP(http), "org/tool")
    assert len(result.items) == 1
    assert result.items[0].kind == "announcement"


@pytest.mark.asyncio
async def test_http_retry_rate_limit_timeout_and_size(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("app.services.evidence_sources.asyncio.sleep", sleep)
    with respx.mock:
        route = respx.get("https://pypi.org/test")
        route.side_effect = [httpx.Response(503), httpx.Response(200, json={"ok": True})]
        async with httpx.AsyncClient() as http:
            client = SourceHTTP(http)
            assert await client.json("https://pypi.org/test") == {"ok": True}
            assert route.call_count == 2
            route.side_effect = None
            route.respond(429, headers={"retry-after": "7200"})
            with pytest.raises(SourceUnavailable) as error:
                await client.json("https://pypi.org/test")
            assert error.value.retry_seconds == 7200
            route.side_effect = httpx.ReadTimeout("test")
            with pytest.raises(SourceUnavailable):
                await client.json("https://pypi.org/test")
            route.side_effect = None
            route.respond(200, content=b"x" * 2_000_001)
            with pytest.raises(SourceUnavailable, match="2 MB"):
                await client.json("https://pypi.org/test")
            with pytest.raises(SourceUnavailable, match="Unapproved"):
                await client.json("http://127.0.0.1/private")


def test_change_thresholds_and_first_observation():
    cfg = Settings()
    assert changes_between("npm", {}, {"downloads": 999999}, cfg) == []
    assert changes_between("npm", {"downloads": 10000}, {"downloads": 10100}, cfg) == []
    assert changes_between("npm", {"downloads": 10000}, {"downloads": 16000}, cfg)[0][0] == (
        "PACKAGE_ADOPTION_INCREASED"
    )
    assert changes_between("github", {"license": "MIT"}, {"license": None}, cfg) == []
    assert changes_between("github", {"dormant": True}, {"dormant": False}, cfg)[0][0] == (
        "PROJECT_RESUMED"
    )


@pytest.mark.asyncio
async def test_deduplication_failure_retention_and_contracts(db_session, client):
    repo = repository()
    other = repository(2, "alternative")
    db_session.add_all([repo, other])
    await db_session.commit()
    cfg = Settings(evidence_retention_days=180)
    item = Evidence(
        external_id="release-1",
        kind="release",
        title="1.0",
        url="https://github.com/org/tool/releases/tag/1.0",
        published_at=datetime.now(UTC),
    )
    observed = Observation(facts={"license": "MIT"}, items=[item])
    for _ in range(2):
        await save_observation(db_session, repo, "github", repo.full_name, observed, 24, cfg)
    await db_session.commit()
    assert await db_session.scalar(select(func.count()).select_from(ExternalEvidenceItem)) == 1
    assert await db_session.scalar(select(func.count()).select_from(RepositoryChangeEvent)) == 1
    await record_failure(
        db_session,
        repo.github_id,
        "github",
        repo.full_name,
        SourceUnavailable("temporarily unavailable"),
    )
    await db_session.commit()
    state = await db_session.get(RepositorySourceState, (1, "github", "org/tool"))
    assert state.last_success_at is not None
    assert state.facts == {"license": "MIT"}
    brief = (await client.get("/api/v2/repositories/org/tool/brief")).json()
    assert brief["synthesis_mode"] == "deterministic"
    assert brief["external_sources"]["sources"][0]["status"] == "degraded"
    assert brief["evidence"][0]["url"] == item.url
    for path in ("evidence", "external-sources"):
        assert (await client.get(f"/api/v2/repositories/org/tool/{path}")).status_code == 200
    changes = await client.get("/api/v2/repositories/by-id/1/changes")
    assert len(changes.json()["items"]) == 1
    assert (await client.get("/api/v2/repositories/by-id/999/changes")).status_code == 404
    comparison = await client.post(
        "/api/v2/compare/context",
        json={
            "github_ids": [1, 2],
            "constraints": {
                "language": "Python",
                "license": "Apache-2.0",
                "deployment": "self-hosted",
            },
        },
    )
    assert comparison.status_code == 200
    fit = comparison.json()["projects"][0]["fit"]
    assert [entry["status"] for entry in fit] == ["matches", "differs", "unknown"]
    assert comparison.json()["recommendation"] is None
    assert (
        await client.post("/api/v2/compare/context", json={"github_ids": [1, 1]})
    ).status_code == 422
    assert (await client.get("/api/v2/topics")).status_code == 200
    topic = (await client.get("/api/v2/topics/agent-frameworks")).json()
    assert len(topic["projects"]) == 2
    assert (await client.get("/api/v2/topics/nonexistent")).status_code == 404
    event = await db_session.scalar(select(RepositoryChangeEvent))
    event.observed_at = datetime.now(UTC) - timedelta(days=181)
    await db_session.commit()
    await prune_evidence(db_session, cfg)
    await db_session.commit()
    assert await db_session.scalar(select(func.count()).select_from(RepositoryChangeEvent)) == 0
