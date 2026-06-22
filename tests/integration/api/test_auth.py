from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_device_workspace_me(client):
    client.headers["X-Device-Fingerprint"] = "test-device"
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"].startswith("device-")
    assert me.json()["can_upload"] is True


@pytest.mark.asyncio
async def test_credential_routes_removed(client):
    for path in (
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    ):
        response = await client.post(path)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
