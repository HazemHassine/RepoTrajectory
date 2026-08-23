"""Add an append-only administrative action audit ledger.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id BIGSERIAL PRIMARY KEY,
            occurred_at TIMESTAMPTZ NOT NULL,
            actor VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            target VARCHAR(511),
            outcome VARCHAR(30) NOT NULL,
            remote_address VARCHAR(100),
            details JSON NOT NULL DEFAULT '{}'::json
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_occurred "
        "ON admin_audit_log(occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_action ON admin_audit_log(action)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_audit_outcome ON admin_audit_log(outcome)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_audit_log")
