import asyncio
import os
import pytest
import pytest_asyncio
from collections.abc import AsyncIterator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.main import app
from app.db.session import get_session

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
