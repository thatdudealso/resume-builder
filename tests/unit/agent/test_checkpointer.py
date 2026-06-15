from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.agent.checkpointer import _to_psycopg_dsn, get_checkpointer


def test_to_psycopg_dsn_converts_asyncpg():
    url = "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    assert _to_psycopg_dsn(url) == "postgresql://user:pass@localhost:5432/mydb"


def test_to_psycopg_dsn_leaves_plain_url_unchanged():
    url = "postgresql://user:pass@localhost:5432/mydb"
    assert _to_psycopg_dsn(url) == url


@pytest.mark.asyncio
async def test_get_checkpointer_calls_setup():
    mock_checkpointer = AsyncMock()
    mock_checkpointer.setup = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.agent.checkpointer.AsyncPostgresSaver.from_conn_string", return_value=mock_cm):
        async with get_checkpointer("postgresql+asyncpg://u:p@localhost/db") as cp:
            assert cp is mock_checkpointer

    mock_checkpointer.setup.assert_awaited_once()
