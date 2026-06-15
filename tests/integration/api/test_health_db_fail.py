from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_db_degraded(client, monkeypatch):
    async def fail_execute(self, *args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.AsyncSession.execute",
        fail_execute,
    )
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db"] is False
    assert body["status"] == "degraded"
