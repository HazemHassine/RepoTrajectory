from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import AdminSession
from app.db.models import AdminAuditLog


def add_admin_audit(
    session: AsyncSession,
    request: Request,
    admin: AdminSession | None,
    action: str,
    *,
    target: str | None = None,
    outcome: str = "accepted",
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AdminAuditLog(
            occurred_at=datetime.now(UTC),
            actor=admin.username if admin else "unauthenticated",
            action=action,
            target=target,
            outcome=outcome,
            remote_address=request.client.host if request.client else None,
            details=details or {},
        )
    )
