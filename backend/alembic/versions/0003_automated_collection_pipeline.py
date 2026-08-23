"""Add automatic discovery, queue, sync state, and compact external activity storage.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS keeps fresh installations safe despite the legacy 0001 migration using
    # live Base.metadata. Existing installations receive the same schema incrementally.
    statements = [
        """
        CREATE TABLE IF NOT EXISTS collections (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            candidate_limit INTEGER NOT NULL DEFAULT 2000,
            active_limit INTEGER NOT NULL DEFAULT 250,
            refresh_hours INTEGER NOT NULL DEFAULT 24,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_candidates (
            id SERIAL PRIMARY KEY,
            github_id BIGINT NOT NULL UNIQUE,
            repository_id INTEGER UNIQUE REFERENCES repositories(id) ON DELETE SET NULL,
            owner VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            full_name VARCHAR(511) NOT NULL UNIQUE,
            description TEXT,
            primary_language VARCHAR(100),
            stars INTEGER NOT NULL DEFAULT 0,
            forks INTEGER NOT NULL DEFAULT 0,
            pushed_at TIMESTAMPTZ,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            is_fork BOOLEAN NOT NULL DEFAULT FALSE,
            source VARCHAR(50) NOT NULL,
            source_score DOUBLE PRECISION NOT NULL DEFAULT 0,
            trend_score DOUBLE PRECISION NOT NULL DEFAULT 0,
            trend_components JSON NOT NULL DEFAULT '{}'::json,
            tier VARCHAR(30) NOT NULL DEFAULT 'candidate',
            eligible BOOLEAN NOT NULL DEFAULT TRUE,
            discovered_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            promoted_at TIMESTAMPTZ,
            next_refresh_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS collection_memberships (
            collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            candidate_id INTEGER NOT NULL REFERENCES repository_candidates(id) ON DELETE CASCADE,
            source VARCHAR(50) NOT NULL,
            score DOUBLE PRECISION NOT NULL DEFAULT 0,
            rank INTEGER,
            selected BOOLEAN NOT NULL DEFAULT FALSE,
            last_ranked_at TIMESTAMPTZ,
            PRIMARY KEY (collection_id, candidate_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id BIGSERIAL PRIMARY KEY,
            job_type VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            candidate_id INTEGER REFERENCES repository_candidates(id) ON DELETE CASCADE,
            repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
            collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
            priority INTEGER NOT NULL DEFAULT 0,
            scheduled_for TIMESTAMPTZ NOT NULL,
            locked_at TIMESTAMPTZ,
            locked_by VARCHAR(255),
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            payload JSON NOT NULL DEFAULT '{}'::json,
            dedupe_key VARCHAR(511) NOT NULL UNIQUE,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_sync_states (
            repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            resource VARCHAR(50) NOT NULL,
            watermark TIMESTAMPTZ,
            etag TEXT,
            last_modified TEXT,
            last_success_at TIMESTAMPTZ,
            next_sync_at TIMESTAMPTZ,
            last_error TEXT,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (repository_id, resource)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS external_repository_activity (
            candidate_id INTEGER NOT NULL REFERENCES repository_candidates(id) ON DELETE CASCADE,
            period_start TIMESTAMPTZ NOT NULL,
            star_events INTEGER NOT NULL DEFAULT 0,
            fork_events INTEGER NOT NULL DEFAULT 0,
            push_events INTEGER NOT NULL DEFAULT 0,
            pull_request_events INTEGER NOT NULL DEFAULT 0,
            issue_events INTEGER NOT NULL DEFAULT 0,
            release_events INTEGER NOT NULL DEFAULT 0,
            weighted_events DOUBLE PRECISION NOT NULL DEFAULT 0,
            PRIMARY KEY (candidate_id, period_start)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS gh_archive_files (
            archive_hour TIMESTAMPTZ PRIMARY KEY,
            status VARCHAR(30) NOT NULL,
            repository_count INTEGER NOT NULL DEFAULT 0,
            event_count BIGINT NOT NULL DEFAULT 0,
            compressed_bytes BIGINT NOT NULL DEFAULT 0,
            processed_at TIMESTAMPTZ,
            last_error TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS collector_state (
            key VARCHAR(100) PRIMARY KEY,
            value JSON NOT NULL DEFAULT '{}'::json,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """,
    ]
    for statement in statements:
        op.execute(statement)

    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_collections_slug ON collections(slug)",
        "CREATE INDEX IF NOT EXISTS ix_collections_enabled ON collections(enabled)",
        "CREATE INDEX IF NOT EXISTS ix_candidate_github_id ON repository_candidates(github_id)",
        "CREATE INDEX IF NOT EXISTS ix_candidate_full_name ON repository_candidates(full_name)",
        (
            "CREATE INDEX IF NOT EXISTS ix_candidate_language "
            "ON repository_candidates(primary_language)"
        ),
        "CREATE INDEX IF NOT EXISTS ix_candidate_stars ON repository_candidates(stars)",
        "CREATE INDEX IF NOT EXISTS ix_candidate_tier ON repository_candidates(tier)",
        (
            "CREATE INDEX IF NOT EXISTS ix_candidate_tier_trend "
            "ON repository_candidates(tier, trend_score)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_candidate_refresh "
            "ON repository_candidates(eligible, next_refresh_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_membership_collection_rank "
            "ON collection_memberships(collection_id, rank)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_job_claim "
            "ON ingestion_jobs(status, scheduled_for, priority)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_job_candidate_status "
            "ON ingestion_jobs(candidate_id, status)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_external_activity_period "
            "ON external_repository_activity(period_start)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS ix_commit_repo_committed "
            "ON commits(repository_id, committed_at)"
        ),
        "CREATE INDEX IF NOT EXISTS ix_pr_repo_created ON pull_requests(repository_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_pr_repo_updated ON pull_requests(repository_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_pr_repo_merged ON pull_requests(repository_id, merged_at)",
        "CREATE INDEX IF NOT EXISTS ix_issue_repo_created ON issues(repository_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_issue_repo_updated ON issues(repository_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_issue_repo_closed ON issues(repository_id, closed_at)",
        (
            "CREATE INDEX IF NOT EXISTS ix_release_repo_published "
            "ON releases(repository_id, published_at)"
        ),
    ]
    for statement in indexes:
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "collector_state",
        "gh_archive_files",
        "external_repository_activity",
        "repository_sync_states",
        "ingestion_jobs",
        "collection_memberships",
        "repository_candidates",
        "collections",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
