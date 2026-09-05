"""Bounded public-source adapters. Facts are normalized before persistence."""

import asyncio
import re
from datetime import datetime
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    external_id: str = Field(max_length=255)
    kind: str
    title: str = Field(max_length=300)
    url: str = Field(max_length=2048)
    excerpt: str | None = Field(default=None, max_length=1200)
    author: str | None = None
    published_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Observation(BaseModel):
    facts: dict[str, Any] = Field(default_factory=dict)
    items: list[Evidence] = Field(default_factory=list)
    repository_urls: list[str] = Field(default_factory=list)


class SourceAdapter(Protocol):
    source: str
    refresh_hours: int

    async def collect(self, client: "SourceHTTP", external_id: str) -> Observation: ...


class SourceUnavailable(RuntimeError):
    def __init__(self, message: str, retry_seconds: int = 3600):
        super().__init__(message)
        self.retry_seconds = retry_seconds


class SourceHTTP:
    """Fixed public hosts only; no arbitrary crawling or persisted raw-response cache."""

    hosts = {
        "registry.npmjs.org",
        "api.npmjs.org",
        "pypi.org",
        "pypistats.org",
        "api.deps.dev",
        "api.osv.dev",
        "hn.algolia.com",
    }

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def json(self, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.hosts:
            raise SourceUnavailable("Unapproved source host")
        for attempt in range(3):
            try:
                async with self.client.stream(
                    "POST" if body is not None else "GET",
                    url,
                    json=body,
                    timeout=12,
                    follow_redirects=False,
                ) as response:
                    if response.status_code == 429:
                        retry = response.headers.get("retry-after", "3600")
                        seconds = int(retry) if retry.isdigit() else 3600
                        raise SourceUnavailable("Source rate limited", max(60, seconds))
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 2_000_000:
                            raise SourceUnavailable("Source response exceeds 2 MB bound")
                    import json

                    result = json.loads(payload)
                    if not isinstance(result, dict):
                        raise SourceUnavailable("Unexpected source response")
                    return result
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                status = (
                    exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                )
                if attempt == 2 or (status is not None and status < 500):
                    raise SourceUnavailable(
                        f"Source request failed ({status or 'timeout/network'})"
                    ) from exc
                await asyncio.sleep(2**attempt)
        raise SourceUnavailable("Source unavailable")


def github_name(url: str) -> str | None:
    cleaned = url.removeprefix("git+").replace("git@github.com:", "https://github.com/")
    parsed = urlsplit(cleaned)
    if parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None
    owner, name = parts[:2]
    name = name.removesuffix(".git")
    if not re.fullmatch(r"[\w.-]+", owner) or not re.fullmatch(r"[\w.-]+", name):
        return None
    return f"{owner}/{name}".casefold()


def package_targets(readme: str) -> list[tuple[str, str]]:
    """Explicit registry URLs only. A mention/name is never a project match."""
    npm = re.findall(r"https://(?:www\.)?npmjs.com/package/(@[\w.-]+/[\w.-]+|[\w.-]+)", readme)
    pypi = re.findall(r"https://pypi.org/project/([\w.-]+)", readme)
    return sorted({*(("npm", p) for p in npm), *(("pypi", p) for p in pypi)})[:4]


class NpmAdapter:
    source = "npm"
    refresh_hours = 24

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        url = f"https://registry.npmjs.org/{quote(external_id, safe='')}/latest"
        data = await client.json(url)
        repository = data.get("repository") or {}
        repo_url = repository.get("url") if isinstance(repository, dict) else repository
        version = str(data.get("version", ""))[:100]
        return Observation(
            repository_urls=[repo_url] if isinstance(repo_url, str) else [],
            facts={
                "package": external_id,
                "version": version,
                "ecosystem": "npm",
                "license": data.get("license") if isinstance(data.get("license"), str) else None,
                "dependencies": list((data.get("dependencies") or {}).keys())[:30],
            },
            items=[
                Evidence(
                    external_id=external_id,
                    kind="package",
                    title=f"{external_id} {version}"[:300],
                    url=f"https://www.npmjs.com/package/{quote(external_id, safe='@/')}",
                )
            ],
        )


class NpmDownloadsAdapter:
    source = "npm_downloads"
    refresh_hours = 168  # compare non-overlapping weekly windows

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        url = f"https://api.npmjs.org/downloads/point/last-week/{quote(external_id, safe='')}"
        data = await client.json(url)
        return Observation(
            facts={
                "downloads": int(data["downloads"]),
                "window": "last-week",
                "start": data["start"],
                "end": data["end"],
                "url": url,
            }
        )


class PypiAdapter:
    source = "pypi"
    refresh_hours = 24

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        data = await client.json(f"https://pypi.org/pypi/{quote(external_id, safe='')}/json")
        info = data["info"]
        version = str(info.get("version", ""))[:100]
        urls = list((info.get("project_urls") or {}).values())
        return Observation(
            repository_urls=[u for u in urls if isinstance(u, str) and github_name(u)],
            facts={
                "package": external_id,
                "version": version,
                "ecosystem": "PyPI",
                "requires_python": info.get("requires_python"),
                "dependencies": (info.get("requires_dist") or [])[:30],
            },
            items=[
                Evidence(
                    external_id=external_id,
                    kind="package",
                    title=f"{external_id} {version}"[:300],
                    url=f"https://pypi.org/project/{quote(external_id, safe='')}/",
                    published_at=next(
                        (u.get("upload_time_iso_8601") for u in data.get("urls", [])[:1]), None
                    ),
                )
            ],
        )


class PypiDownloadsAdapter:
    source = "pypistats"
    refresh_hours = 168

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        url = f"https://pypistats.org/api/packages/{quote(external_id, safe='')}/recent"
        data = await client.json(url)
        return Observation(
            facts={"downloads": int(data["data"]["last_week"]), "window": "last-week", "url": url}
        )


class DepsDevAdapter:
    source = "deps_dev"
    refresh_hours = 168

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        ecosystem, package, version = external_id.split(":", 2)
        url = (
            f"https://api.deps.dev/v3/systems/{ecosystem}/packages/"
            f"{quote(package, safe='')}/versions/{quote(version, safe='')}"
        )
        data = await client.json(url)
        return Observation(
            facts={
                "package": package,
                "version": version,
                "licenses": data.get("licenses", [])[:10],
                "deprecated": data.get("isDeprecated"),
                "url": url,
            },
            items=[
                Evidence(
                    external_id=external_id,
                    kind="dependencies",
                    title=f"Package context for {package} {version}"[:300],
                    url=url,
                    excerpt=str(data.get("deprecatedReason") or "")[:1200] or None,
                )
            ],
        )


class OsvAdapter:
    source = "osv"
    refresh_hours = 24

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        ecosystem, package, version = external_id.split(":", 2)
        data = await client.json(
            "https://api.osv.dev/v1/query",
            {
                "package": {"ecosystem": ecosystem, "name": package},
                "version": version,
            },
        )
        items = []
        for finding in data.get("vulns", [])[:30]:
            fixed = sorted(
                {
                    str(event["fixed"])
                    for affected in finding.get("affected", [])
                    if (affected.get("package") or {}).get("name") == package
                    and (affected.get("package") or {}).get("ecosystem") == ecosystem
                    for span in affected.get("ranges", [])
                    for event in span.get("events", [])
                    if "fixed" in event
                }
            )[:10]
            identifier = str(finding["id"])[:100]
            items.append(
                Evidence(
                    external_id=f"{external_id}:{identifier}"[:255],
                    kind="vulnerability",
                    title=identifier,
                    url=f"https://osv.dev/vulnerability/{quote(identifier, safe='')}",
                    excerpt=str(finding.get("summary") or "")[:1200] or None,
                    published_at=finding.get("published"),
                    details={
                        "package": package,
                        "version": version,
                        "ecosystem": ecosystem,
                        "fixed_versions": fixed,
                        "advisory_id": identifier,
                    },
                )
            )
        return Observation(
            facts={
                "package": package,
                "version": version,
                "ecosystem": ecosystem,
                "finding_ids": [i.title for i in items],
                "checked": True,
                "truncated": len(data.get("vulns", [])) > 30 or bool(data.get("next_page_token")),
            },
            items=items,
        )


class HackerNewsAdapter:
    source = "hacker_news"
    refresh_hours = 72

    async def collect(self, client: SourceHTTP, external_id: str) -> Observation:
        url = (
            "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=20&query="
            + quote(f"github.com/{external_id}", safe="")
        )
        data = await client.json(url)
        items = []
        seen: set[str] = set()
        for hit in data.get("hits", [])[:20]:
            # Search relevance is not entity resolution. Require the exact linked repository.
            if github_name(str(hit.get("url") or "")) != external_id.casefold():
                continue
            target = str(hit.get("url") or "").split("#")[0].rstrip("/").casefold()
            if target in seen:
                continue
            seen.add(target)
            title = str(hit.get("title") or "Repository discussion")[:300]
            kind = "announcement" if title.casefold().startswith("show hn") else "discussion"
            items.append(
                Evidence(
                    external_id=str(hit["objectID"]),
                    kind=kind,
                    title=title,
                    url=(
                        "https://news.ycombinator.com/item?id="
                        + quote(str(hit["objectID"]), safe="")
                    ),
                    author=str(hit.get("author") or "Unknown")[:255],
                    published_at=hit.get("created_at"),
                    details={
                        "attribution": "Hacker News submission; not independently verified",
                        "target_url": target,
                        "comments": hit.get("num_comments"),
                    },
                )
            )
        return Observation(facts={"matched_submissions": len(items)}, items=items)


PACKAGE_ADAPTERS: dict[str, SourceAdapter] = {"npm": NpmAdapter(), "pypi": PypiAdapter()}
