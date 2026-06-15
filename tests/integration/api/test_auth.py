from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_login_me(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "test-device"},
    )
    assert reg.status_code == 200
    assert reg.cookies.get("access_token")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@test.com"


@pytest.mark.asyncio
async def test_refresh_and_logout(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "dev"},
    )
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200


@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
