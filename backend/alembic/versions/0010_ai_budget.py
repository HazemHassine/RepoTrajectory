"""Shared AI reservations, usage ledger and bounded Scout synthesis cache."""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(255), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("artifact", sa.JSON()),
    )
    op.create_index("ix_ai_usage_observed_at", "ai_usage", ["observed_at"])
    op.create_index("ix_ai_usage_fingerprint", "ai_usage", ["fingerprint"])


def downgrade() -> None:
    op.drop_table("ai_usage")
