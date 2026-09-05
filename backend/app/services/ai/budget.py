"""PostgreSQL serializes reservations across the API and collector; failures deny AI."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text

from app.core.config import Settings
from app.db.models import AIUsage
from app.db.session import SessionLocal


async def cached_artifact(key: str) -> dict[str, Any] | None:
    try:
        async with SessionLocal() as session:
            row = await session.scalar(
                select(AIUsage)
                .where(
                    AIUsage.fingerprint == key,
                    AIUsage.status == "completed",
                    AIUsage.operation == "scout",
                    AIUsage.artifact.is_not(None),
                )
                .order_by(AIUsage.observed_at.desc())
                .limit(1)
            )
            return row.artifact if row else None
    except Exception:
        return None


async def reserve(
    cfg: Settings, provider: str, model: str, operation: str, key: str, tokens: int
) -> str | None:
    if not cfg.ai_enabled or not cfg.effective_ai_api_key:
        return None
    try:
        async with SessionLocal() as session, session.begin():
            # A transaction-scoped lock coordinates the two processes without Redis.
            await session.execute(text("SELECT pg_advisory_xact_lock(91873412)"))
            now = datetime.now(UTC)
            daily = await session.scalar(
                select(func.count())
                .select_from(AIUsage)
                .where(
                    AIUsage.observed_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                )
            )
            monthly = await session.scalar(
                select(func.sum(AIUsage.reserved_tokens)).where(
                    AIUsage.observed_at
                    >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                )
            )
            running = await session.scalar(
                select(func.count())
                .select_from(AIUsage)
                .where(
                    AIUsage.status == "reserved",
                    AIUsage.expires_at > now,
                )
            )
            if (
                (daily or 0) >= cfg.ai_daily_request_limit
                or (monthly or 0) + tokens > cfg.ai_monthly_token_limit
                or (running or 0) >= cfg.ai_max_concurrency
            ):
                return None
            identifier = str(uuid4())
            session.add(
                AIUsage(
                    id=identifier,
                    provider=provider[:255],
                    model=model[:100],
                    operation=operation,
                    observed_at=now,
                    expires_at=now + timedelta(seconds=90),
                    status="reserved",
                    reserved_tokens=tokens,
                    fingerprint=key,
                )
            )
            return identifier
    except Exception:
        return None


async def finish(identifier: str, cfg: Settings, payload: dict[str, Any] | None) -> None:
    try:
        async with SessionLocal() as session, session.begin():
            row = await session.get(AIUsage, identifier)
            if row is None:
                return
            row.status = "completed" if payload else "failed"
            usage = (payload or {}).get("usage", {})
            row.input_tokens = usage.get("prompt_tokens")
            row.output_tokens = usage.get("completion_tokens")
            # Keep the conservative reservation on failures or incomplete usage reporting.
            if row.input_tokens is not None and row.output_tokens is not None:
                row.reserved_tokens = max(row.reserved_tokens, row.input_tokens + row.output_tokens)
                if (
                    cfg.ai_input_price_per_million is not None
                    and cfg.ai_output_price_per_million is not None
                ):
                    row.estimated_cost = (
                        row.input_tokens * cfg.ai_input_price_per_million
                        + row.output_tokens * cfg.ai_output_price_per_million
                    ) / 1e6
            if payload and row.operation == "scout" and len(json.dumps(payload)) <= 20000:
                row.artifact = payload
    except Exception:
        # The reservation remains charged and expires; availability never depends on ledger writes.
        return
