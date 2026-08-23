from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.github.client import GitHubAPIError, GitHubClient, GitHubRateLimitError


@pytest.mark.asyncio
@respx.mock
async def test_pagination_follows_link_header() -> None:
    first = "https://api.github.com/repos/acme/tool/issues"
    second = f"{first}?page=2"
    respx.get(first, params={"per_page": 100}).mock(
        return_value=httpx.Response(
            200, json=[{"id": 1}], headers={"Link": f'<{second}>; rel="next"'}
        )
    )
    respx.get(second).mock(return_value=httpx.Response(200, json=[{"id": 2}]))
    async with GitHubClient(None) as client:
        assert [item["id"] async for item in client.paginate("/repos/acme/tool/issues")] == [1, 2]


@pytest.mark.asyncio
@respx.mock
async def test_api_error_is_explicit() -> None:
    respx.get("https://api.github.com/repos/nope/missing").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    async with GitHubClient(None) as client:
        with pytest.raises(GitHubAPIError, match="Not Found"):
            await client.get_json("/repos/nope/missing")


@pytest.mark.asyncio
@respx.mock
async def test_repository_redirect_is_followed() -> None:
    old_url = "https://api.github.com/repos/old-owner/project"
    new_url = "https://api.github.com/repositories/42"
    respx.get(old_url).mock(return_value=httpx.Response(301, headers={"Location": new_url}))
    respx.get(new_url).mock(
        return_value=httpx.Response(200, json={"id": 42, "full_name": "new-owner/project"})
    )
    async with GitHubClient(None) as client:
        payload = await client.get_json("/repos/old-owner/project")
    assert payload == {"id": 42, "full_name": "new-owner/project"}


@pytest.mark.asyncio
@respx.mock
async def test_search_paginates_to_the_requested_bound() -> None:
    endpoint = "https://api.github.com/search/repositories"
    first = [{"id": index} for index in range(100)]
    second = [{"id": index} for index in range(100, 150)]
    respx.get(
        endpoint,
        params={
            "q": "language:Python",
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
            "page": 1,
        },
    ).mock(return_value=httpx.Response(200, json={"items": first}))
    respx.get(
        endpoint,
        params={
            "q": "language:Python",
            "sort": "stars",
            "order": "desc",
            "per_page": 50,
            "page": 2,
        },
    ).mock(return_value=httpx.Response(200, json={"items": second}))

    async with GitHubClient(None) as client:
        result = await client.search_repositories("language:Python", 150)

    assert len(result) == 150
    assert result[-1]["id"] == 149


@pytest.mark.asyncio
async def test_rate_reserve_scales_to_small_search_bucket() -> None:
    async with GitHubClient(None, rate_limit_reserve=100) as client:
        client.rate.limit = 30
        client.rate.remaining = 2
        client.rate.reset_at = datetime.now(UTC) + timedelta(minutes=1)
        await client._respect_limits()
        client.rate.remaining = 1
        with pytest.raises(GitHubRateLimitError, match=r"reserve \(1\)"):
            await client._respect_limits()
