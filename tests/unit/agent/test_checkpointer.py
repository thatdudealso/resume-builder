from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest

from packages.agent.checkpointer import (
    _to_psycopg_dsn,
    ensure_checkpointer_schema,
    get_checkpointer,
)


def test_to_psycopg_dsn_converts_asyncpg():
    url = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    assert _to_psycopg_dsn(url) == "postgresql://user:pass@localhost:5432/mydb"


def test_to_psycopg_dsn_leaves_plain_url_unchanged():
    url = "postgresql://user:pass@localhost:5432/mydb"
    assert _to_psycopg_dsn(url) == url


@pytest.mark.asyncio
async def test_get_checkpointer_does_not_call_setup():
    mock_checkpointer = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "packages.agent.checkpointer.ensure_checkpointer_schema",
            new=AsyncMock(),
        ),
        patch(
            "packages.agent.checkpointer.AsyncPostgresSaver.from_conn_string",
            return_value=mock_cm,
        ),
    ):
        async with get_checkpointer("postgresql+asyncpg://u:p@localhost/db") as cp:
            assert cp is mock_checkpointer

    mock_checkpointer.setup.assert_not_called()


@pytest.mark.asyncio
async def test_current_schema_version_handles_missing_table():
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock(
        side_effect=psycopg.errors.UndefinedTable("relation does not exist")
    )
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "packages.agent.checkpointer.psycopg.AsyncConnection.connect",
        new=AsyncMock(return_value=mock_conn),
    ):
        from packages.agent.checkpointer import _current_schema_version

        version = await _current_schema_version("postgresql://u:p@localhost/db")

    assert version == -1


@pytest.mark.asyncio
async def test_ensure_checkpointer_schema_applies_pending_migrations():
    with patch(
        "packages.agent.checkpointer._apply_pending_migrations",
        new=AsyncMock(),
    ) as mock_apply:
        await ensure_checkpointer_schema("postgresql+asyncpg://u:p@localhost/db")
        await ensure_checkpointer_schema("postgresql+asyncpg://u:p@localhost/db")

    mock_apply.assert_awaited_once()
