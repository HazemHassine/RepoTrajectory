"""Run only against a disposable *_radar_test database after alembic upgrade head."""
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from sqlalchemy import func, select, text

from app.core.config import Settings, get_settings
from app.db.models import (
    AIUsage, CatalogRepository, ExternalEvidenceItem, IngestionJob,
    RepositoryChangeEvent, RepositoryEmbedding, RepositorySearchDocument,
)
from app.db.session import SessionLocal
from app.services.ai.budget import finish, reserve
from app.services.ai.fallback_provider import FallbackAIProvider
from app.services.collector import CollectorWorker, enqueue_job
from app.services.evidence import save_observation
from app.services.evidence_sources import Evidence, Observation
from app.services.search import hybrid_search


class MockSemanticProvider(FallbackAIProvider):
    semantic_available = True

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1535 for _ in texts]


async def main() -> None:
    assert get_settings().database_url.endswith("_radar_test"), "Use isolated test database only"
    now = datetime.now(UTC)
    cfg = Settings(ai_enabled=True, ai_api_key="test-only", ai_max_concurrency=1)
    async with SessionLocal() as session:
        await session.execute(text("DELETE FROM ai_usage"))
        repo = CatalogRepository(
            github_id=900100, owner="test", name="radar", full_name="test/radar",
            description="Python agent framework", primary_language="Python", license="MIT",
            created_at=now, updated_at=now, last_discovered_at=now, last_observed_at=now,
        )
        session.add(repo)
        await session.flush()
        session.add(RepositorySearchDocument(
            github_id=repo.github_id, full_name=repo.full_name, name=repo.name, owner=repo.owner,
            description=repo.description, primary_language="Python", updated_at=now,
        ))
        session.add(RepositoryEmbedding(
            github_id=repo.github_id, embedding_version=cfg.ai_embedding_version,
            model=cfg.ai_embedding_model, embedding=[1.0] + [0.0] * 1535,
            created_at=now, updated_at=now,
        ))
        await session.commit()
        result = await hybrid_search(session, "python agent", settings=cfg,
                                     ai_provider=MockSemanticProvider())
        assert result["semantic_available"] and result["items"][0]["github_id"] == repo.github_id
        result = await hybrid_search(session, "python agent", settings=cfg,
                                     ai_provider=FallbackAIProvider())
        assert not result["semantic_available"] and result["items"]
        observation = Observation(items=[Evidence(
            external_id="r1", kind="release", title="v1", url="https://github.com/test/radar",
            published_at=now,
        )])
        for _ in range(2):
            await save_observation(session, repo, "github", repo.full_name, observation, 24, cfg)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(ExternalEvidenceItem)) == 1
        assert await session.scalar(select(func.count()).select_from(RepositoryChangeEvent)) == 1
        one = await enqueue_job(session, "maintenance", "radar-test-one")
        assert one == await enqueue_job(session, "maintenance", "radar-test-one")
        two = await enqueue_job(session, "maintenance", "radar-test-two")
        await session.commit()
    async with SessionLocal() as lock_session:
        await lock_session.scalar(select(IngestionJob).where(IngestionJob.id == one)
                                  .with_for_update())
        async with SessionLocal() as worker_session:
            worker = CollectorWorker(AsyncMock(), AsyncMock(), worker_id="radar-check")
            claimed = await worker._claim(worker_session)
            assert claimed is not None and claimed.id == two
        await lock_session.rollback()
    first, second = await asyncio.gather(
        reserve(cfg, "test", "test", "scout", "a" * 64, 100),
        reserve(cfg, "test", "test", "scout", "b" * 64, 100),
    )
    assert sum(item is not None for item in (first, second)) == 1
    await finish(first or second or "", cfg, {"usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    assert await reserve(cfg.model_copy(update={"ai_daily_request_limit": 1}),
                         "test", "test", "scout", "c" * 64, 100) is None
    assert await reserve(cfg.model_copy(update={"ai_monthly_token_limit": 100}),
                         "test", "test", "scout", "d" * 64, 1) is None
    async with SessionLocal() as session:
        indexes = await session.scalar(text(
            "SELECT count(*) FROM pg_indexes WHERE indexname IN "
            "('ix_change_repo_time', 'ix_evidence_repo_observed', 'ix_ai_usage_fingerprint')"
        ))
        assert indexes == 3
        assert await session.scalar(select(func.count()).select_from(AIUsage)) == 1
    print("PASS: pgvector, lexical fallback, evidence replay, indexes, SKIP LOCKED, AI budget concurrency")


if __name__ == "__main__":
    asyncio.run(main())
