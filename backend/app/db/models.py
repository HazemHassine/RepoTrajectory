from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(511), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stars: Mapped[int] = mapped_column(default=0)
    forks: Mapped[int] = mapped_column(default=0)
    watchers: Mapped[int] = mapped_column(default=0)
    open_issues: Mapped[int] = mapped_column(default=0)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    primary_language: Mapped[str | None] = mapped_column(String(100))
    license: Mapped[str | None] = mapped_column(String(100))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("owner", "name", name="uq_repository_owner_name"),)


class RepositorySnapshot(Base):
    __tablename__ = "repository_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stars: Mapped[int]
    forks: Mapped[int]
    open_issues: Mapped[int]
    watchers: Mapped[int]
    contributor_count: Mapped[int | None]
    __table_args__ = (Index("ix_snapshot_repo_captured", "repository_id", "captured_at"),)


class Contributor(Base):
    __tablename__ = "contributors"
    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    html_url: Mapped[str | None] = mapped_column(Text)
    contributor_type: Mapped[str | None] = mapped_column(String(50))


class RepositoryContributor(Base):
    __tablename__ = "repository_contributors"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    contributor_id: Mapped[int] = mapped_column(
        ForeignKey("contributors.id", ondelete="CASCADE"), primary_key=True
    )
    contributions: Mapped[int] = mapped_column(default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Commit(Base):
    __tablename__ = "commits"
    sha: Mapped[str] = mapped_column(String(40), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("contributors.id"))
    author_login: Mapped[str | None] = mapped_column(String(255))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (Index("ix_commit_repo_committed", "repository_id", "committed_at"),)


class PullRequest(Base):
    __tablename__ = "pull_requests"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(primary_key=True)
    author_login: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    additions: Mapped[int | None]
    deletions: Mapped[int | None]
    changed_files: Mapped[int | None]

    __table_args__ = (
        Index("ix_pr_repo_created", "repository_id", "created_at"),
        Index("ix_pr_repo_updated", "repository_id", "updated_at"),
        Index("ix_pr_repo_merged", "repository_id", "merged_at"),
    )


class Issue(Base):
    __tablename__ = "issues"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    number: Mapped[int] = mapped_column(primary_key=True)
    author_login: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    comments: Mapped[int] = mapped_column(default=0)
    labels: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    __table_args__ = (
        Index("ix_issue_repo_created", "repository_id", "created_at"),
        Index("ix_issue_repo_updated", "repository_id", "updated_at"),
        Index("ix_issue_repo_closed", "repository_id", "closed_at"),
    )


class Release(Base):
    __tablename__ = "releases"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    github_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prerelease: Mapped[bool] = mapped_column(default=False)
    draft: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (Index("ix_release_repo_published", "repository_id", "published_at"),)


class RepositoryLanguage(Base):
    __tablename__ = "repository_languages"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(100), primary_key=True)
    bytes: Mapped[int] = mapped_column(BigInteger)


class RepositoryTopic(Base):
    __tablename__ = "repository_topics"
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    topic: Mapped[str] = mapped_column(String(100), primary_key=True)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_days: Mapped[int] = mapped_column(Integer, default=30)
    momentum_score: Mapped[float] = mapped_column(Float)
    health_score: Mapped[float] = mapped_column(Float)
    bus_factor_risk: Mapped[float] = mapped_column(Float)
    components: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (Index("ix_metric_repo_calculated", "repository_id", "calculated_at"),)


class Collection(Base):
    """A durable discovery universe with its own promotion and refresh policy."""

    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    candidate_limit: Mapped[int] = mapped_column(Integer, default=2000)
    active_limit: Mapped[int] = mapped_column(Integer, default=250)
    refresh_hours: Mapped[int] = mapped_column(Integer, default=24)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RepositoryCandidate(Base):
    """A lightweight repository record discovered before expensive REST hydration."""

    __tablename__ = "repository_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), unique=True, index=True
    )
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(511), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    primary_language: Mapped[str | None] = mapped_column(String(100), index=True)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    classification: Mapped[str] = mapped_column(String(50), default="unclassified", index=True)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    stars: Mapped[int] = mapped_column(Integer, default=0, index=True)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), index=True)
    source_score: Mapped[float] = mapped_column(Float, default=0)
    trend_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    trend_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tier: Mapped[str] = mapped_column(String(30), default="candidate", index=True)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_candidate_tier_trend", "tier", "trend_score"),
        Index("ix_candidate_refresh", "eligible", "next_refresh_at"),
        Index("ix_candidate_classification_tier", "classification", "tier"),
    )


class CollectionMembership(Base):
    __tablename__ = "collection_memberships"

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("repository_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(50))
    score: Mapped[float] = mapped_column(Float, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_ranked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_membership_collection_rank", "collection_id", "rank"),)


class IngestionJob(Base):
    """PostgreSQL-backed, leaseable work item. One bad repository cannot stop a batch."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("repository_candidates.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[int | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(511), unique=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_job_claim", "status", "scheduled_for", "priority"),
        Index("ix_job_candidate_status", "candidate_id", "status"),
    )


class RepositorySyncState(Base):
    __tablename__ = "repository_sync_states"

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    resource: Mapped[str] = mapped_column(String(50), primary_key=True)
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExternalRepositoryActivity(Base):
    """Compact hourly GH Archive facts; raw public event payloads are intentionally discarded."""

    __tablename__ = "external_repository_activity"

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("repository_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    star_events: Mapped[int] = mapped_column(Integer, default=0)
    fork_events: Mapped[int] = mapped_column(Integer, default=0)
    push_events: Mapped[int] = mapped_column(Integer, default=0)
    pull_request_events: Mapped[int] = mapped_column(Integer, default=0)
    issue_events: Mapped[int] = mapped_column(Integer, default=0)
    release_events: Mapped[int] = mapped_column(Integer, default=0)
    weighted_events: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (Index("ix_external_activity_period", "period_start"),)


class GhArchiveFile(Base):
    __tablename__ = "gh_archive_files"

    archive_hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    algorithm_version: Mapped[str] = mapped_column(String(20), default="1")
    status: Mapped[str] = mapped_column(String(30), index=True)
    repository_count: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(BigInteger, default=0)
    compressed_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CollectorState(Base):
    __tablename__ = "collector_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(511))
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    remote_address: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
