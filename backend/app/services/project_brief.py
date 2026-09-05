from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.product_schemas import (
    BriefResponse,
    ChangeResponse,
    CompareConstraints,
    ConstraintResult,
    EvidenceResponse,
    ExternalSourcesResponse,
    Fact,
    LinkResponse,
    SourceResponse,
)
from app.db.models import (
    CatalogRepository,
    ExternalEvidenceItem,
    RepositoryChangeEvent,
    RepositoryExternalLink,
    RepositorySourceState,
)
from app.services.evidence import fingerprint, utc


async def external_sources(session: AsyncSession, gid: int) -> ExternalSourcesResponse:
    links = (
        await session.scalars(
            select(RepositoryExternalLink)
            .where(
                RepositoryExternalLink.github_id == gid,
            )
            .limit(12)
        )
    ).all()
    states = (
        await session.scalars(
            select(RepositorySourceState)
            .where(
                RepositorySourceState.github_id == gid,
            )
            .order_by(RepositorySourceState.last_attempt_at.desc())
            .limit(40)
        )
    ).all()
    return ExternalSourcesResponse(
        links=[LinkResponse.model_validate(link) for link in links],
        sources=[
            SourceResponse(
                source=state.source,
                external_id=state.external_id,
                status="degraded"
                if state.last_error
                else ("stale" if utc(state.next_refresh_at) < datetime.now(UTC) else "healthy"),
                last_success_at=state.last_success_at,
                last_error=state.last_error,
                next_refresh_at=state.next_refresh_at,
                facts=state.facts,
            )
            for state in states
        ],
    )


async def build_brief(session: AsyncSession, repo: CatalogRepository) -> BriefResponse:
    url = f"https://github.com/{repo.full_name}"
    sources = await external_sources(session, repo.github_id)
    evidence = (
        await session.scalars(
            select(ExternalEvidenceItem)
            .where(
                ExternalEvidenceItem.github_id == repo.github_id,
            )
            .order_by(ExternalEvidenceItem.observed_at.desc(), ExternalEvidenceItem.id.desc())
            .limit(60)
        )
    ).all()
    changes = (
        await session.scalars(
            select(RepositoryChangeEvent)
            .where(
                RepositoryChangeEvent.github_id == repo.github_id,
            )
            .order_by(RepositoryChangeEvent.occurred_at.desc())
            .limit(15)
        )
    ).all()

    def fact(label: str, value: str | None, source: str = url) -> Fact:
        return Fact(
            label=label,
            value=value,
            source_url=source if value is not None else None,
            observed_at=repo.last_observed_at,
            basis="direct" if value is not None else "missing",
        )

    facts = [
        fact("Primary language", repo.primary_language),
        fact("License identifier", repo.license, url + "/blob/" + repo.default_branch + "/LICENSE"),
        fact("Project-declared topics", ", ".join(repo.topics) or None),
        fact("GitHub attention (stars, not users)", str(repo.stars)),
        fact("Last repository push", repo.pushed_at.isoformat() if repo.pushed_at else None),
        fact("Getting started", "Open the project's README", url + "#readme"),
    ]
    missing = [
        "Deployment requirements and operational complexity have not been verified.",
        "Suitability and undocumented capabilities require a hands-on evaluation.",
    ]
    if not sources.links:
        missing.append(
            "No verified package linkage; package adoption and security coverage are missing."
        )
    for state in sources.sources:
        if state.source in {"npm_downloads", "pypistats"} and state.last_success_at:
            facts.append(
                Fact(
                    label=f"Weekly downloads · {state.external_id} (not users)",
                    value=str(state.facts.get("downloads")),
                    source_url=state.facts.get("url"),
                    observed_at=state.last_success_at,
                )
            )
        if state.source == "osv" and state.last_success_at:
            ids = state.facts.get("finding_ids", [])
            facts.append(
                Fact(
                    label=f"OSV check · {state.external_id}",
                    value=(
                        ", ".join(ids)
                        if ids
                        else "No known findings returned for this checked package version"
                    )
                    + ("; result truncated" if state.facts.get("truncated") else ""),
                    source_url="https://osv.dev",
                    observed_at=state.last_success_at,
                )
            )
        if state.status != "healthy":
            missing.append(f"{state.source}: {state.last_error or 'refresh overdue'}")
    return BriefResponse(
        github_id=repo.github_id,
        full_name=repo.full_name,
        description=fact("What the project says it does", repo.description),
        readme_excerpt=fact("Project README excerpt", repo.readme_excerpt, url + "#readme"),
        facts=facts,
        missing=missing,
        external_sources=sources,
        evidence=[EvidenceResponse.model_validate(item) for item in evidence],
        changes=[ChangeResponse.model_validate(item) for item in changes],
        evidence_fingerprint=fingerprint(
            repo.description,
            repo.readme_excerpt,
            [f.model_dump() for f in facts],
            [(e.fingerprint, e.details) for e in evidence],
        ),
    )


def evaluate_constraints(
    repo: CatalogRepository, brief: BriefResponse, constraints: CompareConstraints
) -> list[ConstraintResult]:
    results = []
    url = f"https://github.com/{repo.full_name}"
    for label, wanted, actual in (
        ("Primary language", constraints.language, repo.primary_language),
        ("License identifier", constraints.license, repo.license),
    ):
        if wanted:
            results.append(
                ConstraintResult(
                    constraint=label,
                    status="unknown"
                    if not actual
                    else ("matches" if actual.casefold() == wanted.casefold() else "differs"),
                    explanation=f"Requested {wanted}; recorded {actual or 'Unknown'}.",
                    source_url=url if actual else None,
                )
            )
    if constraints.package_ecosystem:
        matched = any(
            link.source == constraints.package_ecosystem and link.verification == "verified"
            for link in brief.external_sources.links
        )
        results.append(
            ConstraintResult(
                constraint="Package ecosystem",
                status="matches" if matched else "unknown",
                explanation="Verified package link available."
                if matched
                else "No verified package link.",
                source_url=next(
                    (
                        link.canonical_url
                        for link in brief.external_sources.links
                        if link.source == constraints.package_ecosystem
                    ),
                    None,
                ),
            )
        )
    if constraints.activity_within_days:
        active = (
            (datetime.now(UTC) - utc(repo.pushed_at)).days <= constraints.activity_within_days
            if repo.pushed_at
            else None
        )
        results.append(
            ConstraintResult(
                constraint="Recent push",
                status="unknown" if active is None else ("matches" if active else "differs"),
                explanation=f"Requested push within {constraints.activity_within_days} days; "
                f"recorded {repo.pushed_at or 'Unknown'}. A push is not a release.",
                source_url=url,
            )
        )
    if constraints.deployment:
        results.append(
            ConstraintResult(
                constraint="Deployment preference",
                status="unknown",
                explanation=(
                    f"{constraints.deployment}: deployment requirements have not been verified."
                ),
            )
        )
    return results
