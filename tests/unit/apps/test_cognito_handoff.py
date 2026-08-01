from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_redirect_uses_allowlisted_callback(client, monkeypatch):
    from apps.web.config import settings

    monkeypatch.setattr(settings, "public_base_url", "https://resumebild.5432wire.com")
    monkeypatch.setattr(settings, "auth_login_url", "https://5432wire.com/login")
    monkeypatch.setattr(
        settings,
        "auth_return_allowlist",
        "https://resumebild.5432wire.com",
    )
    resp = await client.get("/api/v1/auth/login-redirect", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://5432wire.com/login?")
    assert "return_url=" in location


@pytest.mark.asyncio
async def test_cognito_exchange_requires_config(client, monkeypatch):
    from apps.web.config import settings

    monkeypatch.setattr(settings, "cognito_user_pool_id", "")
    monkeypatch.setattr(settings, "cognito_app_client_id", "")
    resp = await client.post("/api/v1/auth/cognito/exchange", json={"id_token": "x" * 40})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cognito_exchange_sets_cookies(client, monkeypatch):
    from apps.web.config import settings

    monkeypatch.setattr(settings, "cognito_user_pool_id", "us-east-1_test")
    monkeypatch.setattr(settings, "cognito_app_client_id", "client-test")

    def fake_decode(token: str):
        assert token.startswith("good-token")
        return {"sub": "cognito-sub-1", "email": "crew@example.com"}

    monkeypatch.setattr("apps.web.api.v1.auth.decode_cognito_jwt", fake_decode)
    resp = await client.post(
        "/api/v1/auth/cognito/exchange",
        json={"id_token": "good-token-" + ("x" * 32)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "crew@example.com"
    assert "access_token=" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_auth_callback_page(client):
    resp = await client.get("/auth/callback")
    assert resp.status_code == 200
    assert "Finishing sign-in" in resp.text
