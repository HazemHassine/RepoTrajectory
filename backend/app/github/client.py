import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class GitHubAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"GitHub API {status_code}: {message}")
        self.status_code = status_code


class GitHubRateLimitError(GitHubAPIError):
    def __init__(self, reset_at: datetime | None, message: str = "rate limit exhausted") -> None:
        super().__init__(403, message)
        self.reset_at = reset_at


@dataclass(slots=True)
class GitHubRateState:
    limit: int | None = None
    remaining: int | None = None
    used: int | None = None
    reset_at: datetime | None = None
    resource: str | None = None
    request_count: int = 0


class GitHubClient:
    def __init__(
        self,
        token: str | None,
        base_url: str = "https://api.github.com",
        max_retries: int = 3,
        request_interval_seconds: float = 0,
        rate_limit_reserve: int = 0,
    ) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # GitHub returns permanent redirects when a repository is renamed or transferred.
        # Following GET redirects lets callers continue using an old owner/name safely and
        # ensures ingestion stores the canonical full_name returned by the final response.
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=30,
            follow_redirects=True,
        )
        self.max_retries = max_retries
        self.request_interval_seconds = max(0, request_interval_seconds)
        self.rate_limit_reserve = max(0, rate_limit_reserve)
        self.rate = GitHubRateState()
        self._last_request_at = 0.0
        self._request_lock = asyncio.Lock()

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            async with self._request_lock:
                await self._respect_limits()
                response = await self.client.get(path, params=params)
                self._last_request_at = monotonic()
                self._update_rate_state(response)
            remaining = response.headers.get("x-ratelimit-remaining")
            log.debug("github_request", path=path, status=response.status_code, remaining=remaining)
            if response.status_code < 400:
                return response
            if response.status_code == 403 and remaining == "0":
                raise GitHubRateLimitError(self.rate.reset_at)
            secondary_limited = response.status_code in {403, 429} and (
                response.headers.get("retry-after") is not None
                or "secondary rate limit" in response.text.casefold()
            )
            if (
                response.status_code in {429, 500, 502, 503, 504} or secondary_limited
            ) and attempt < self.max_retries:
                retry_after = response.headers.get("retry-after")
                delay = min(float(retry_after), 60) if retry_after else min(2**attempt, 30)
                await asyncio.sleep(delay)
                continue
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GitHubAPIError(response.status_code, message)
        raise AssertionError("unreachable")

    async def post(self, path: str, json_data: dict[str, Any] | None = None) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            async with self._request_lock:
                await self._respect_limits()
                response = await self.client.post(path, json=json_data)
                self._last_request_at = monotonic()
                self._update_rate_state(response)
            remaining = response.headers.get("x-ratelimit-remaining")
            log.debug("github_post", path=path, status=response.status_code, remaining=remaining)
            if response.status_code < 400:
                return response
            if response.status_code == 403 and remaining == "0":
                raise GitHubRateLimitError(self.rate.reset_at)
            secondary_limited = response.status_code in {403, 429} and (
                response.headers.get("retry-after") is not None
                or "secondary rate limit" in response.text.casefold()
            )
            if (
                response.status_code in {429, 500, 502, 503, 504} or secondary_limited
            ) and attempt < self.max_retries:
                retry_after = response.headers.get("retry-after")
                delay = min(float(retry_after), 60) if retry_after else min(2**attempt, 30)
                await asyncio.sleep(delay)
                continue
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GitHubAPIError(response.status_code, message)
        raise AssertionError("unreachable")

    async def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.post("/graphql", json_data={"query": query, "variables": variables or {}})
        payload = response.json()
        if "errors" in payload and not payload.get("data"):
            raise GitHubAPIError(200, str(payload["errors"]))
        return payload

    async def graphql_batch_repositories(
        self, repositories: list[tuple[str, str]]
    ) -> dict[str, dict[str, Any]]:
        """Batch fetch lightweight metadata for up to 50 repositories in a single GraphQL query."""
        if not repositories:
            return {}
        query_parts = ["query {"]
        for idx, (owner, name) in enumerate(repositories):
            # Escape owner and name
            safe_owner = owner.replace('"', '\\"')
            safe_name = name.replace('"', '\\"')
            query_parts.append(
                f"""
                r{idx}: repository(owner: "{safe_owner}", name: "{safe_name}") {{
                    databaseId
                    name
                    owner {{ login }}
                    description
                    stargazerCount
                    forkCount
                    watchers {{ totalCount }}
                    issues(states: OPEN) {{ totalCount }}
                    pushedAt
                    isArchived
                    isFork
                    primaryLanguage {{ name }}
                    licenseInfo {{ spdxId }}
                    defaultBranchRef {{ name }}
                    repositoryTopics(first: 10) {{
                        nodes {{ topic {{ name }} }}
                    }}
                }}
                """
            )
        query_parts.append("}")
        query = "\n".join(query_parts)
        payload = await self.graphql(query)
        data = payload.get("data", {})
        results: dict[str, dict[str, Any]] = {}
        for idx, (owner, name) in enumerate(repositories):
            repo_data = data.get(f"r{idx}")
            if repo_data and repo_data.get("databaseId"):
                full_name = f"{repo_data['owner']['login']}/{repo_data['name']}"
                topics = [
                    node["topic"]["name"]
                    for node in (repo_data.get("repositoryTopics") or {}).get("nodes", [])
                    if node.get("topic")
                ]
                results[full_name] = {
                    "id": repo_data["databaseId"],
                    "owner": {"login": repo_data["owner"]["login"]},
                    "name": repo_data["name"],
                    "full_name": full_name,
                    "description": repo_data.get("description"),
                    "stargazers_count": repo_data.get("stargazerCount", 0),
                    "forks_count": repo_data.get("forkCount", 0),
                    "subscribers_count": (repo_data.get("watchers") or {}).get("totalCount", 0),
                    "open_issues_count": (repo_data.get("issues") or {}).get("totalCount", 0),
                    "pushed_at": repo_data.get("pushedAt"),
                    "archived": repo_data.get("isArchived", False),
                    "fork": repo_data.get("isFork", False),
                    "language": (repo_data.get("primaryLanguage") or {}).get("name"),
                    "license": {"spdx_id": (repo_data.get("licenseInfo") or {}).get("spdxId")},
                    "default_branch": (repo_data.get("defaultBranchRef") or {}).get("name", "main"),
                    "topics": topics,
                }
        return results

    async def _respect_limits(self) -> None:
        effective_reserve = (
            min(self.rate_limit_reserve, max(1, int(self.rate.limit * 0.02)))
            if self.rate.limit
            else self.rate_limit_reserve
        )
        if (
            self.rate.remaining is not None
            and self.rate.remaining <= effective_reserve
            and self.rate.reset_at
            and self.rate.reset_at > datetime.now(UTC)
        ):
            raise GitHubRateLimitError(
                self.rate.reset_at,
                f"rate budget reached reserve ({effective_reserve}) for "
                f"{self.rate.resource or 'unknown'} bucket",
            )
        elapsed = monotonic() - self._last_request_at
        delay = self.request_interval_seconds - elapsed
        if delay > 0:
            await asyncio.sleep(delay)

    def _update_rate_state(self, response: httpx.Response) -> None:
        def integer(name: str) -> int | None:
            value = response.headers.get(name)
            return int(value) if value and value.isdigit() else None

        reset = integer("x-ratelimit-reset")
        self.rate.limit = integer("x-ratelimit-limit") or self.rate.limit
        self.rate.remaining = integer("x-ratelimit-remaining")
        self.rate.used = integer("x-ratelimit-used")
        self.rate.reset_at = datetime.fromtimestamp(reset, UTC) if reset else self.rate.reset_at
        self.rate.resource = response.headers.get("x-ratelimit-resource") or self.rate.resource
        self.rate.request_count += 1

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return (await self.get(path, params)).json()

    async def get_json_conditional(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> tuple[Any | None, httpx.Headers]:
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        response = await self.get_with_headers(path, params, headers)
        return (None if response.status_code == 304 else response.json()), response.headers

    async def get_with_headers(
        self,
        path: str,
        params: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        # Conditional requests use the same retry/rate machinery as regular GETs. Keeping this
        # method small avoids caching mutable paginated responses in application memory.
        for attempt in range(self.max_retries + 1):
            async with self._request_lock:
                await self._respect_limits()
                response = await self.client.get(path, params=params, headers=headers)
                self._last_request_at = monotonic()
                self._update_rate_state(response)
            if response.status_code < 400:
                return response
            remaining = response.headers.get("x-ratelimit-remaining")
            if response.status_code == 403 and remaining == "0":
                raise GitHubRateLimitError(self.rate.reset_at)
            retry_after = response.headers.get("retry-after")
            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                await asyncio.sleep(min(float(retry_after), 60) if retry_after else 2**attempt)
                continue
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GitHubAPIError(response.status_code, message)
        raise AssertionError("unreachable")

    async def paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        query: dict[str, Any] | None = {**(params or {}), "per_page": 100}
        url: str | None = path
        while url:
            response = await self.get(url, query)
            payload = response.json()
            if not isinstance(payload, list):
                raise GitHubAPIError(response.status_code, "expected a paginated list response")
            for item in payload:
                yield item
            url = response.links.get("next", {}).get("url")
            query = None

    async def paginate_pages(
        self, path: str, params: dict[str, Any] | None = None, max_items: int | None = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        seen = 0
        query: dict[str, Any] | None = {**(params or {}), "per_page": 100}
        url: str | None = path
        while url and (max_items is None or seen < max_items):
            response = await self.get(url, query)
            payload = response.json()
            if not isinstance(payload, list):
                raise GitHubAPIError(response.status_code, "expected a paginated list response")
            page = payload if max_items is None else payload[: max_items - seen]
            if page:
                yield page
                seen += len(page)
            url = response.links.get("next", {}).get("url")
            query = None

    async def search_repositories(
        self, query: str, max_results: int = 100, sort: str = "stars"
    ) -> list[dict[str, Any]]:
        target = min(max(max_results, 1), 1000)
        results: list[dict[str, Any]] = []
        page = 1
        while len(results) < target:
            payload = await self.get_json(
                "/search/repositories",
                {
                    "q": query,
                    "sort": sort,
                    "order": "desc",
                    "per_page": min(100, target - len(results)),
                    "page": page,
                },
            )
            items = payload.get("items", [])
            if not items:
                break
            results.extend(items[: target - len(results)])
            if len(items) < min(100, target - len(results) + len(items)):
                break
            page += 1
        return results

    @staticmethod
    def parse_last_modified(value: str | None) -> object | None:
        return parsedate_to_datetime(value) if value else None
