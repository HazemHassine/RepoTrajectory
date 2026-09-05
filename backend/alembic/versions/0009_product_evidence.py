"""Normalized evidence, shared source health, snapshots and deterministic changes.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def identity() -> sa.Column:
    return sa.Column(
        "github_id",
        sa.BigInteger(),
        sa.ForeignKey("catalog_repositories.github_id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "repository_external_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        identity(),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("match_method", sa.String(80), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("verification", sa.String(30), nullable=False),
        sa.Column("provenance_url", sa.String(2048), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("github_id", "source", "external_id", name="uq_external_link"),
    )
    op.create_index(
        "ix_repository_external_links_github_id", "repository_external_links", ["github_id"]
    )
    op.create_table(
        "external_evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        identity(),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("excerpt", sa.String(1200)),
        sa.Column("author", sa.String(255)),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("github_id", "fingerprint", name="uq_evidence_fingerprint"),
    )
    op.create_index(
        "ix_evidence_repo_observed", "external_evidence_items", ["github_id", "observed_at"]
    )
    op.create_index("ix_evidence_retention", "external_evidence_items", ["observed_at"])
    gid = identity()
    gid.primary_key = True
    op.create_table(
        "repository_source_states",
        gid,
        sa.Column("source", sa.String(30), primary_key=True),
        sa.Column("external_id", sa.String(255), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(500)),
        sa.Column("facts", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_repository_source_states_next_refresh_at",
        "repository_source_states",
        ["next_refresh_at"],
    )
    op.create_table(
        "repository_source_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        identity(),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "github_id", "source", "external_id", "captured_at", name="uq_source_snapshot_day"
        ),
    )
    op.create_index(
        "ix_repository_source_snapshots_captured_at", "repository_source_snapshots", ["captured_at"]
    )
    op.create_index(
        "ix_source_snapshot_repo_time", "repository_source_snapshots", ["github_id", "captured_at"]
    )
    op.create_table(
        "repository_change_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        identity(),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "evidence_id",
            sa.Integer(),
            sa.ForeignKey("external_evidence_items.id", ondelete="SET NULL"),
        ),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("github_id", "fingerprint", name="uq_change_fingerprint"),
    )
    op.create_index("ix_change_repo_time", "repository_change_events", ["github_id", "occurred_at"])
    op.create_index(
        "ix_repository_change_events_observed_at", "repository_change_events", ["observed_at"]
    )


def downgrade() -> None:
    for table in (
        "repository_change_events",
        "repository_source_snapshots",
        "repository_source_states",
        "external_evidence_items",
        "repository_external_links",
    ):
        op.drop_table(table)
