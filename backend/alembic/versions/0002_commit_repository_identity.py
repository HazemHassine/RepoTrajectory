"""Scope commit identity to a repository.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("commits_pkey", "commits", type_="primary")
    op.create_primary_key("commits_pkey", "commits", ["repository_id", "sha"])


def downgrade() -> None:
    op.drop_constraint("commits_pkey", "commits", type_="primary")
    op.create_primary_key("commits_pkey", "commits", ["sha"])
