from __future__ import annotations

from apps.web.api.v1.auth import build_login_redirect_url, is_allowed_return_url
from apps.web.config import settings


def test_return_url_allowlist(monkeypatch):
    monkeypatch.setattr(
        settings,
        "auth_return_allowlist",
        "https://resumebild.5432wire.com,http://localhost:8000",
    )
    assert is_allowed_return_url("https://resumebild.5432wire.com/auth/callback")
    assert is_allowed_return_url("http://localhost:8000/auth/callback")
    assert not is_allowed_return_url("https://evil.example/phish")
    assert not is_allowed_return_url("https://resumebild.5432wire.com.evil/x")
    assert not is_allowed_return_url("javascript:alert(1)")


def test_build_login_redirect_url(monkeypatch):
    monkeypatch.setattr(settings, "auth_login_url", "https://5432wire.com/login")
    monkeypatch.setattr(
        settings,
        "auth_return_allowlist",
        "https://resumebild.5432wire.com",
    )
    url = build_login_redirect_url("https://resumebild.5432wire.com/auth/callback")
    assert url.startswith("https://5432wire.com/login?")
    assert "return_url=https%3A%2F%2Fresumebild.5432wire.com%2Fauth%2Fcallback" in url
