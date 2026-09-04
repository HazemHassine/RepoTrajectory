"""Deduplicate ingestion_jobs and reindex table.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DELETE FROM ingestion_jobs
            WHERE id IN (
              SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                         PARTITION BY dedupe_key
                         ORDER BY CASE WHEN status = 'completed' THEN 1 WHEN status = 'running' THEN 2 ELSE 3 END,
                                  attempts DESC,
                                  id ASC
                       ) as rn
                FROM ingestion_jobs
              ) t
              WHERE t.rn > 1
            );
            """
        )
        op.execute("REINDEX TABLE ingestion_jobs;")


def downgrade() -> None:
    pass
