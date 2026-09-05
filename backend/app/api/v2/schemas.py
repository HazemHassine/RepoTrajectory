from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScoutCardSummary(BaseModel):
    promise_score: float
    quantitative_score: float = 0.0
    ai_score: float = 0.0
    confidence: float = 0.0
    why_it_surfaced: str
    supporting_facts: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    score_components: dict[str, Any] = Field(default_factory=dict)
    model_identity: str = ""
    created_at: datetime | None = None


class CatalogRepositorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    github_id: int
    owner: str
    name: str
    full_name: str
    description: str | None = None
    primary_language: str | None = None
    license: str | None = None
    default_branch: str = "main"
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None
    tier: str = "candidate"
    is_directory: bool = False
    is_deep: bool = False
    classification: str = "unclassified"
    classification_confidence: float = 0.0
    topics: list[str] = Field(default_factory=list)
    selection_score: float = 0.0
    promise_score: float | None = None
    scout_eligible: bool = True
    scout: ScoutCardSummary | None = None
    lens_metrics: dict[str, Any] = Field(default_factory=dict)


class CursorPaginationEnvelope(BaseModel):
    items: list[CatalogRepositorySummary]
    next_cursor: str | None = None
    total_count: int = 0
    lens: str = "developer"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    filters: dict[str, Any] | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class SearchItem(BaseModel):
    github_id: int
    owner: str
    name: str
    full_name: str
    description: str | None = None
    primary_language: str | None = None
    license: str | None = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    pushed_at: str | None = None
    created_at: str | None = None
    tier: str = "candidate"
    is_directory: bool = False
    is_deep: bool = False
    classification: str = "software"
    topics: list[str] = Field(default_factory=list)
    selection_score: float = 0.0
    promise_score: float | None = None
    scout: dict[str, Any] | None = None
    search_rrf_score: float = 0.0


class SearchResponse(BaseModel):
    items: list[SearchItem]
    next_cursor: str | None = None
    total_count: int = 0
    interpreted_filters: dict[str, Any] = Field(default_factory=dict)
    result_rationale: str = ""
    evidence_freshness: str = ""
    semantic_available: bool = False


class ScoutFeedItem(BaseModel):
    github_id: int
    owner: str
    name: str
    full_name: str
    description: str | None = None
    primary_language: str | None = None
    license: str | None = None
    stars: int = 0
    forks: int = 0
    pushed_at: datetime | None = None
    topics: list[str] = Field(default_factory=list)
    promise_score: float
    confidence: float
    why_it_surfaced: str
    supporting_facts: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    score_components: dict[str, Any] = Field(default_factory=dict)


class ScoutFeedResponse(BaseModel):
    items: list[ScoutFeedItem]
    next_cursor: str | None = None
    total_count: int = 0


class FacetCount(BaseModel):
    name: str
    count: int


class FacetsResponse(BaseModel):
    languages: list[FacetCount]
    categories: list[FacetCount]
    licenses: list[FacetCount]
    evidence_levels: dict[str, int]
    freshness_counts: dict[str, int]


class UnifiedRepositoryProfile(BaseModel):
    catalog: CatalogRepositorySummary
    scout: ScoutCardSummary | None = None
    deep_evidence: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    readme_excerpt: str | None = None


class HealthV2Response(BaseModel):
    status: str
    ai_service: dict[str, Any]
    database: dict[str, Any]
    directory_count: int
    candidate_count: int
    deep_cohort_count: int
    degraded_features: list[str] = Field(default_factory=list)
