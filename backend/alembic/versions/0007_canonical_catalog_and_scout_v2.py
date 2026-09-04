"""Canonical catalog, vector embeddings, Scout assessments, and lossless backfill.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Try enabling PostgreSQL extensions if supported by host
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        pass

    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception:
        pass

    statements = [
        """
        CREATE TABLE IF NOT EXISTS catalog_repositories (
            github_id BIGINT PRIMARY KEY,
            owner VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            full_name VARCHAR(511) NOT NULL UNIQUE,
            description TEXT,
            primary_language VARCHAR(100),
            license VARCHAR(100),
            default_branch VARCHAR(255) NOT NULL DEFAULT 'main',
            stars INTEGER NOT NULL DEFAULT 0,
            forks INTEGER NOT NULL DEFAULT 0,
            watchers INTEGER NOT NULL DEFAULT 0,
            open_issues INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            pushed_at TIMESTAMPTZ,
            archived BOOLEAN NOT NULL DEFAULT FALSE,
            is_fork BOOLEAN NOT NULL DEFAULT FALSE,
            tier VARCHAR(30) NOT NULL DEFAULT 'candidate',
            is_directory BOOLEAN NOT NULL DEFAULT FALSE,
            is_deep BOOLEAN NOT NULL DEFAULT FALSE,
            classification VARCHAR(50) NOT NULL DEFAULT 'unclassified',
            classification_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            rejection_reason TEXT,
            topics JSON NOT NULL DEFAULT '[]'::json,
            activity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            popularity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            freshness_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            maintenance_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            selection_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            scout_eligible BOOLEAN NOT NULL DEFAULT TRUE,
            promise_score DOUBLE PRECISION,
            content_hash VARCHAR(64),
            readme_excerpt TEXT,
            last_discovered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            next_refresh_at TIMESTAMPTZ,
            repository_id INTEGER UNIQUE REFERENCES repositories(id) ON DELETE SET NULL,
            provenance JSON NOT NULL DEFAULT '{}'::json
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_search_documents (
            github_id BIGINT PRIMARY KEY REFERENCES catalog_repositories(github_id) ON DELETE CASCADE,
            full_name VARCHAR(511) NOT NULL,
            name VARCHAR(255) NOT NULL,
            owner VARCHAR(255) NOT NULL,
            description TEXT,
            topics_text TEXT NOT NULL DEFAULT '',
            primary_language VARCHAR(100),
            license VARCHAR(100),
            readme_text TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_signal_snapshots (
            id BIGSERIAL PRIMARY KEY,
            github_id BIGINT NOT NULL REFERENCES catalog_repositories(github_id) ON DELETE CASCADE,
            captured_at TIMESTAMPTZ NOT NULL,
            stars INTEGER NOT NULL DEFAULT 0,
            forks INTEGER NOT NULL DEFAULT 0,
            open_issues INTEGER NOT NULL DEFAULT 0,
            watchers INTEGER NOT NULL DEFAULT 0,
            velocity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            source VARCHAR(50) NOT NULL DEFAULT 'github_rest'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_embeddings (
            id BIGSERIAL PRIMARY KEY,
            github_id BIGINT NOT NULL REFERENCES catalog_repositories(github_id) ON DELETE CASCADE,
            embedding_version VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS scout_assessments (
            id BIGSERIAL PRIMARY KEY,
            github_id BIGINT NOT NULL REFERENCES catalog_repositories(github_id) ON DELETE CASCADE,
            version INTEGER NOT NULL DEFAULT 1,
            promise_score DOUBLE PRECISION NOT NULL,
            quantitative_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            ai_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            rationale TEXT NOT NULL DEFAULT '',
            why_it_surfaced TEXT NOT NULL DEFAULT '',
            supporting_facts JSON NOT NULL DEFAULT '[]'::json,
            uncertainty TEXT,
            risk_flags JSON NOT NULL DEFAULT '[]'::json,
            score_components JSON NOT NULL DEFAULT '{}'::json,
            evidence_references JSON NOT NULL DEFAULT '{}'::json,
            model_identity VARCHAR(100) NOT NULL DEFAULT '',
            prompt_version VARCHAR(50) NOT NULL DEFAULT 'v1',
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            is_current BOOLEAN NOT NULL DEFAULT TRUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repository_provenance (
            id BIGSERIAL PRIMARY KEY,
            github_id BIGINT NOT NULL,
            field_name VARCHAR(100) NOT NULL,
            source VARCHAR(50) NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            details JSON NOT NULL DEFAULT '{}'::json
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS query_embedding_cache (
            normalized_query VARCHAR(511) NOT NULL,
            model VARCHAR(100) NOT NULL,
            embedding JSON NOT NULL DEFAULT '[]'::json,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (normalized_query, model)
        )
        """,
    ]

    for statement in statements:
        op.execute(statement)

    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_catalog_owner ON catalog_repositories(owner)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_full_name ON catalog_repositories(full_name)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_language ON catalog_repositories(primary_language)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_stars ON catalog_repositories(stars)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_pushed_at ON catalog_repositories(pushed_at)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_tier ON catalog_repositories(tier)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_is_directory ON catalog_repositories(is_directory)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_is_deep ON catalog_repositories(is_deep)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_selection ON catalog_repositories(selection_score DESC)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_dir_selection ON catalog_repositories(is_directory, selection_score DESC)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_scout_promise ON catalog_repositories(scout_eligible, promise_score DESC)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_tier_pushed ON catalog_repositories(tier, pushed_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_lang_stars ON catalog_repositories(primary_language, stars DESC)",
        "CREATE INDEX IF NOT EXISTS ix_catalog_refresh ON catalog_repositories(next_refresh_at)",
        "CREATE INDEX IF NOT EXISTS ix_search_doc_name ON repository_search_documents(full_name)",
        "CREATE INDEX IF NOT EXISTS ix_signal_snapshot_captured ON repository_signal_snapshots(github_id, captured_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_embedding_repo_version ON repository_embeddings(github_id, embedding_version)",
        "CREATE INDEX IF NOT EXISTS ix_scout_repo_current ON scout_assessments(github_id, is_current)",
        "CREATE INDEX IF NOT EXISTS ix_scout_current_promise ON scout_assessments(is_current, promise_score DESC)",
        "CREATE INDEX IF NOT EXISTS ix_provenance_repo_field ON repository_provenance(github_id, field_name)",
    ]

    for index_stmt in indexes:
        op.execute(index_stmt)

    # Lossless backfill from existing repositories and repository_candidates
    # 1. Backfill from hydrated repositories
    op.execute(
        """
        INSERT INTO catalog_repositories (
            github_id, owner, name, full_name, description, primary_language,
            license, default_branch, stars, forks, watchers, open_issues,
            created_at, updated_at, pushed_at, archived, is_fork, tier,
            is_directory, is_deep, classification, classification_confidence,
            topics, activity_score, popularity_score, freshness_score,
            maintenance_score, selection_score, scout_eligible,
            last_discovered_at, last_observed_at, repository_id, provenance
        )
        SELECT
            r.github_id, r.owner, r.name, r.full_name, r.description, r.primary_language,
            r.license, r.default_branch, r.stars, r.forks, r.watchers, r.open_issues,
            r.created_at, r.updated_at, r.pushed_at, r.archived, FALSE,
            'deep', TRUE, TRUE, 'software', 1.0,
            '[]'::json, 50.0, LEAST(100.0, r.stars / 100.0), 50.0, 50.0, 60.0, TRUE,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, r.id,
            json_build_object('source', 'backfill_repository', 'observed_at', CURRENT_TIMESTAMP)
        FROM repositories r
        ON CONFLICT (github_id) DO UPDATE SET
            repository_id = EXCLUDED.repository_id,
            is_deep = TRUE,
            tier = 'deep';
        """
    )

    # 2. Backfill from repository_candidates
    op.execute(
        """
        INSERT INTO catalog_repositories (
            github_id, owner, name, full_name, description, primary_language,
            license, default_branch, stars, forks, watchers, open_issues,
            created_at, updated_at, pushed_at, archived, is_fork, tier,
            is_directory, is_deep, classification, classification_confidence,
            rejection_reason, topics, activity_score, popularity_score,
            freshness_score, maintenance_score, selection_score, scout_eligible,
            last_discovered_at, last_observed_at, next_refresh_at, repository_id, provenance
        )
        SELECT
            c.github_id, c.owner, c.name, c.full_name, c.description, c.primary_language,
            NULL, 'main', c.stars, c.forks, 0, 0,
            c.discovered_at, c.last_seen_at, c.pushed_at, c.archived, c.is_fork,
            CASE WHEN c.tier IN ('active', 'pinned') THEN 'directory' ELSE 'candidate' END,
            CASE WHEN c.tier IN ('active', 'pinned') THEN TRUE ELSE FALSE END,
            CASE WHEN c.repository_id IS NOT NULL THEN TRUE ELSE FALSE END,
            c.classification, c.classification_confidence,
            c.rejection_reason, c.topics,
            c.trend_score, LEAST(100.0, c.stars / 100.0), 50.0, 50.0,
            c.trend_score,
            CASE WHEN c.is_fork OR c.archived THEN FALSE ELSE TRUE END,
            c.discovered_at, c.last_seen_at, c.next_refresh_at, c.repository_id,
            json_build_object('source', c.source, 'observed_at', c.last_seen_at)
        FROM repository_candidates c
        ON CONFLICT (github_id) DO UPDATE SET
            classification = EXCLUDED.classification,
            classification_confidence = EXCLUDED.classification_confidence,
            rejection_reason = EXCLUDED.rejection_reason,
            topics = EXCLUDED.topics,
            repository_id = COALESCE(catalog_repositories.repository_id, EXCLUDED.repository_id),
            is_deep = (catalog_repositories.is_deep OR EXCLUDED.is_deep);
        """
    )

    # 3. Populate search documents from catalog
    op.execute(
        """
        INSERT INTO repository_search_documents (
            github_id, full_name, name, owner, description, topics_text,
            primary_language, license, readme_text, updated_at
        )
        SELECT
            c.github_id, c.full_name, c.name, c.owner, c.description,
            COALESCE(array_to_string(ARRAY(SELECT json_array_elements_text(c.topics)), ' '), ''),
            c.primary_language, c.license, '', CURRENT_TIMESTAMP
        FROM catalog_repositories c
        ON CONFLICT (github_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    tables = [
        "query_embedding_cache",
        "repository_provenance",
        "scout_assessments",
        "repository_embeddings",
        "repository_signal_snapshots",
        "repository_search_documents",
        "catalog_repositories",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
