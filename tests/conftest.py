from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("NOWPAYMENTS_API_KEY", "test")

from packages.db.base import Base
import packages.db.models  # noqa: F401


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    from apps.web import dependencies as deps
    from apps.web.main import create_app
    import packages.db.session as db_session

    app = create_app()

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db_session.SessionLocal = maker

    async def override_db():
        async with maker() as session:
            yield session

    class FakeRedis:
        store: dict = {}

        async def incr(self, key: str) -> int:
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]

        async def expire(self, key: str, ttl: int) -> None:
            pass

        async def ping(self) -> bool:
            return True

    fake_redis = FakeRedis()

    async def override_redis():
        return fake_redis

    app.dependency_overrides[deps.get_db] = override_db
    app.dependency_overrides[deps.get_redis] = override_redis
    monkeypatch.setattr(deps, "get_redis", override_redis)
    monkeypatch.setattr("apps.web.middleware.rate_limit.get_redis", override_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
