from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

_setup_lock = asyncio.Lock()
_schema_ready = False


def _to_psycopg_dsn(database_url: str) -> str:
    """Convert SQLAlchemy asyncpg URL to psycopg3 DSN.

    langgraph-checkpoint-postgres requires psycopg3, not asyncpg.
    e.g. postgresql+asyncpg://user:pass@host/db → postgresql://user:pass@host/db
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _current_schema_version(dsn: str) -> int:
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute("SELECT v FROM checkpoint_migrations ORDER BY v DESC LIMIT 1")
            except psycopg.errors.UndefinedTable:
                return -1
            row = await cur.fetchone()
            return int(row[0]) if row else -1


async def _apply_pending_migrations(dsn: str) -> None:
    """Apply langgraph checkpoint migrations one at a time.

    CREATE INDEX CONCURRENTLY cannot run inside a transaction and deadlocks when
    multiple setup() calls race. Run each migration in autocommit mode instead.
    """
    latest = len(AsyncPostgresSaver.MIGRATIONS) - 1
    version = await _current_schema_version(dsn)
    if version >= latest:
        logger.info("LangGraph checkpoint schema already at v%s", version)
        return

    logger.info("LangGraph checkpoint schema at v%s; applying through v%s", version, latest)
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        async with conn.cursor() as cur:
            for v, migration in enumerate(
                AsyncPostgresSaver.MIGRATIONS,
                start=0,
            ):
                if v <= version:
                    continue
                logger.info("Applying LangGraph checkpoint migration v%s", v)
                await cur.execute(migration)
                await cur.execute("INSERT INTO checkpoint_migrations (v) VALUES (%s)", (v,))
    logger.info("LangGraph checkpoint schema ready at v%s", latest)


async def ensure_checkpointer_schema(database_url: str) -> None:
    """Ensure langgraph checkpoint tables and migrations exist (once per process)."""
    global _schema_ready
    if _schema_ready:
        return
    async with _setup_lock:
        if _schema_ready:
            return
        dsn = _to_psycopg_dsn(database_url)
        await _apply_pending_migrations(dsn)
        _schema_ready = True


@asynccontextmanager
async def get_checkpointer(database_url: str) -> AsyncGenerator[AsyncPostgresSaver, None]:
    """Yield a Postgres checkpointer with schema ensured exactly once."""
    await ensure_checkpointer_schema(database_url)
    dsn = _to_psycopg_dsn(database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
        yield checkpointer
