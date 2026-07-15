from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_app_load_sets_fingerprint_cookie(client):
    resp = await client.get("/app/")
    assert "rb_device_fingerprint=" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_auth_me_ok_with_that_cookie(client):
    load = await client.get("/app/")
    cookie = load.cookies.get("rb_device_fingerprint")
    assert cookie
    me = await client.get("/api/v1/auth/me", cookies={"rb_device_fingerprint": cookie})
    assert me.status_code == 200
