from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    owner: str
    name: str
    full_name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    stars: int
    forks: int
    watchers: int
    open_issues: int
    default_branch: str
    primary_language: str | None
    license: str | None
    archived: bool
    pushed_at: datetime | None
    last_ingested_at: datetime | None


class MetricResponse(BaseModel):
    repository: str
    calculated_at: datetime | None
    window_days: int
    momentum_score: float | None
    health_score: float | None
    bus_factor_risk: float | None
    components: dict[str, Any]


class ActivityPoint(BaseModel):
    period: datetime
    commits: int = 0
    merged_prs: int = 0
    issues_closed: int = 0
    releases: int = 0


class HistoryPoint(BaseModel):
    captured_at: datetime
    stars: int
    forks: int
    open_issues: int
    watchers: int


class ContributorResponse(BaseModel):
    login: str
    contributions: int
    avatar_url: str | None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    github_id: int
    repository_id: int | None
    owner: str
    name: str
    full_name: str
    description: str | None
    primary_language: str | None
    topics: list[str]
    classification: str
    classification_confidence: float
    rejection_reason: str | None
    stars: int
    forks: int
    pushed_at: datetime | None
    source: str
    source_score: float
    trend_score: float
    trend_components: dict[str, Any]
    tier: str
    eligible: bool
    discovered_at: datetime
    last_seen_at: datetime
    promoted_at: datetime | None
    next_refresh_at: datetime | None


class CollectionResponse(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    candidate_limit: int
    active_limit: int
    refresh_hours: int
    enabled: bool
    candidate_count: int
    selected_count: int
    updated_at: datetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_type: str
    status: str
    candidate_id: int | None
    repository_id: int | None
    priority: int
    scheduled_for: datetime
    locked_at: datetime | None
    locked_by: str | None
    attempts: int
    max_attempts: int
    payload: dict[str, Any]
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CollectorOverviewResponse(BaseModel):
    tiers: dict[str, int]
    classifications: dict[str, int]
    jobs: dict[str, int]
    github_rate: dict[str, Any]
    last_archive_hour: datetime | None
    archive_hours_processed: int
    archive_events_processed: int
    archive_compressed_bytes: int
    external_activity_rows: int
    hydrated_repositories: int
    database_size_bytes: int | None
    oldest_queued_at: datetime | None
    last_completed_at: datetime | None


class QueueRepositoryRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=511, pattern=r"^[^/\s]+/[^/\s]+$")


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class AdminSessionResponse(BaseModel):
    username: str
    csrf_token: str
    issued_at: datetime
    expires_at: datetime


class AdminAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor: str
    action: str
    target: str | None
    outcome: str
    remote_address: str | None
    details: dict[str, Any]
