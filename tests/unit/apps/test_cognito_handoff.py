from __future__ import annotations

import pytest
from sqlalchemy import select

from apps.web.dependencies import get_or_create_cognito_user
from packages.core.security.jwt import register_user
from packages.db.models.user import User


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
        return {"sub": "cognito-sub-1", "email": "crew@example.com", "email_verified": True}

    monkeypatch.setattr("apps.web.api.v1.auth.decode_cognito_jwt", fake_decode)
    resp = await client.post(
        "/api/v1/auth/cognito/exchange",
        json={"id_token": "good-token-" + ("x" * 32)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "crew@example.com"
    cookie_header = resp.headers.get("set-cookie", "").lower()
    assert "access_token=" in cookie_header
    assert "httponly" in cookie_header
    # Cookies issued after the handoff must remain scoped to ResumeBild rather
    # than sharing browser tokens with 5432wire subdomains.
    assert "domain=" not in cookie_header


@pytest.mark.asyncio
async def test_unverified_cognito_email_does_not_link_existing_user(session):
    existing = await register_user(session, "victim@example.com", "password123")
    await session.flush()

    user = await get_or_create_cognito_user(
        session,
        {"sub": "unverified-sub", "email": "victim@example.com", "email_verified": False},
    )

    assert user.id != existing.id
    assert user.email == "cognito-unverified-sub@resume-builder.local"
    result = await session.execute(select(User).where(User.id == existing.id))
    assert result.scalar_one().cognito_sub is None


@pytest.mark.asyncio
async def test_auth_callback_page(client):
    resp = await client.get("/auth/callback")
    assert resp.status_code == 200
    assert "Finishing sign-in" in resp.text
