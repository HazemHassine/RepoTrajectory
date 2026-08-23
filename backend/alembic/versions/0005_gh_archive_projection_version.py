"""Version compact GH Archive projections so selection changes can replay safely.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE gh_archive_files ADD COLUMN IF NOT EXISTS "
        "algorithm_version VARCHAR(20) NOT NULL DEFAULT '1'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE gh_archive_files DROP COLUMN IF EXISTS algorithm_version")
