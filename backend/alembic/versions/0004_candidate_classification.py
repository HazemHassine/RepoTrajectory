"""Add lightweight repository classification before expensive hydration.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE repository_candidates "
        "ADD COLUMN IF NOT EXISTS topics JSON NOT NULL DEFAULT '[]'::json"
    )
    op.execute(
        "ALTER TABLE repository_candidates "
        "ADD COLUMN IF NOT EXISTS classification VARCHAR(50) NOT NULL "
        "DEFAULT 'unclassified'"
    )
    op.execute(
        "ALTER TABLE repository_candidates "
        "ADD COLUMN IF NOT EXISTS classification_confidence DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE repository_candidates ADD COLUMN IF NOT EXISTS rejection_reason TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_classification "
        "ON repository_candidates(classification)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_classification_tier "
        "ON repository_candidates(classification, tier)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_candidate_classification_tier")
    op.execute("DROP INDEX IF EXISTS ix_candidate_classification")
    op.execute("ALTER TABLE repository_candidates DROP COLUMN IF EXISTS rejection_reason")
    op.execute("ALTER TABLE repository_candidates DROP COLUMN IF EXISTS classification_confidence")
    op.execute("ALTER TABLE repository_candidates DROP COLUMN IF EXISTS classification")
    op.execute("ALTER TABLE repository_candidates DROP COLUMN IF EXISTS topics")
