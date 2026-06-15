from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def _to_psycopg_dsn(database_url: str) -> str:
    """Convert SQLAlchemy asyncpg URL to psycopg3 DSN.

    langgraph-checkpoint-postgres requires psycopg3, not asyncpg.
    e.g. postgresql+asyncpg://user:pass@host/db → postgresql://user:pass@host/db
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def get_checkpointer(database_url: str) -> AsyncGenerator[AsyncPostgresSaver, None]:
    """Yield a ready-to-use Postgres checkpointer.

    Calls setup() once per context to ensure the langgraph checkpoint tables
    (checkpoints, checkpoint_blobs, checkpoint_writes) exist. These are managed
    by langgraph internally — not via Alembic.
    """
    dsn = _to_psycopg_dsn(database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
