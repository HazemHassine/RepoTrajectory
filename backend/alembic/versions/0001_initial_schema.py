"""Initial normalized GitHub and analytics schema.

Revision ID: 0001
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Frozen initial schema: importing live ORM metadata breaks fresh migration chains.
    schema = Path(__file__).with_name("0001_schema.sql").read_text()
    for statement in schema.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in (
        "metric_snapshots",
        "repository_topics",
        "repository_languages",
        "releases",
        "issues",
        "pull_requests",
        "commits",
        "repository_contributors",
        "repository_snapshots",
        "contributors",
        "repositories",
    ):
        op.drop_table(table)
