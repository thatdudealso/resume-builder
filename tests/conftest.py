from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("NOWPAYMENTS_API_KEY", "test")

import packages.db.models  # noqa: F401
import packages.integrations.hf_inference as hf_inference
from packages.db.base import Base


@pytest.fixture(autouse=True)
def reset_hf_circuit_breaker() -> None:
    hf_inference._circuit_open_until = 0.0
    hf_inference._failure_count = 0


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    db_url = os.environ["DATABASE_URL"]
    is_sqlite = db_url.startswith("sqlite")
    kwargs: dict[str, object] = {"echo": False}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    engine = create_async_engine(db_url, **kwargs)
    async with engine.begin() as conn:
        if is_sqlite:
            # SQLite in-memory: create schema fresh each test.
            await conn.run_sync(Base.metadata.create_all)
        else:
            # PostgreSQL in CI: schema already created by the migrate service
            # (Alembic). Truncate all tables to get a clean slate without
            # touching constraint definitions (avoids CircularDependencyError
            # and named-constraint mismatches from use_alter).
            table_names = ", ".join(
                f'"{t.name}"' for t in Base.metadata.sorted_tables
            )
            await conn.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )
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
    import packages.db.session as db_session
    from apps.web import dependencies as deps
    from apps.web.main import create_app

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
