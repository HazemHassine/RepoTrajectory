from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Fact(BaseModel):
    label: str
    value: str | None
    source_url: str | None = None
    observed_at: datetime | None = None
    basis: Literal["direct", "derived", "attributed", "missing"] = "direct"


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    kind: str
    title: str
    excerpt: str | None
    author: str | None
    url: str
    published_at: datetime | None
    observed_at: datetime
    details: dict[str, Any]


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    title: str
    evidence_id: int | None
    source_url: str
    occurred_at: datetime
    observed_at: datetime


class ChangesResponse(BaseModel):
    items: list[ChangeResponse]
    retention_start: datetime
    truncated: bool = False


class LinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: str
    external_id: str
    canonical_url: str
    match_method: str
    match_confidence: float
    verification: str
    provenance_url: str
    observed_at: datetime


class SourceResponse(BaseModel):
    source: str
    external_id: str
    status: Literal["healthy", "stale", "degraded"]
    last_success_at: datetime | None
    last_error: str | None
    next_refresh_at: datetime
    facts: dict[str, Any]


class ExternalSourcesResponse(BaseModel):
    links: list[LinkResponse]
    sources: list[SourceResponse]


class BriefResponse(BaseModel):
    github_id: int
    full_name: str
    description: Fact
    readme_excerpt: Fact
    facts: list[Fact]
    missing: list[str]
    evidence: list[EvidenceResponse]
    changes: list[ChangeResponse]
    external_sources: ExternalSourcesResponse
    evidence_fingerprint: str
    synthesis_mode: Literal["deterministic"] = "deterministic"


class CompareConstraints(BaseModel):
    context: str = Field(default="", max_length=2000)
    language: str | None = Field(default=None, max_length=100)
    license: str | None = Field(default=None, max_length=100)
    package_ecosystem: Literal["npm", "pypi"] | None = None
    activity_within_days: int | None = Field(default=None, ge=1, le=730)
    deployment: Literal["self-hosted", "saas-acceptable"] | None = None


class CompareRequest(BaseModel):
    github_ids: list[int] = Field(min_length=2, max_length=4)
    constraints: CompareConstraints = Field(default_factory=CompareConstraints)


class ConstraintResult(BaseModel):
    constraint: str
    status: Literal["matches", "differs", "unknown"]
    explanation: str
    source_url: str | None = None


class ComparedProject(BaseModel):
    brief: BriefResponse
    fit: list[ConstraintResult]


class CompareResponse(BaseModel):
    constraints: CompareConstraints
    projects: list[ComparedProject]
    recommendation: str | None = None
    synthesis_mode: Literal["structured"] = "structured"
    limitation: str = (
        "Free-text context is saved in this view; "
        "only explicit structured constraints are evaluated."
    )


class TopicResponse(BaseModel):
    slug: str
    name: str
    description: str
    terms: list[str]


class TopicProject(BaseModel):
    github_id: int
    full_name: str
    description: str | None
    primary_language: str | None
    matched_terms: list[str]
    pushed_at: datetime | None
    stars: int


class TopicDetail(BaseModel):
    topic: TopicResponse
    projects: list[TopicProject]
    changes: list[ChangeResponse]
    limit: int = 60
