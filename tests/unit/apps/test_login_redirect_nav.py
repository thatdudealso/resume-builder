from __future__ import annotations

from apps.web.ui.auth_guard import LOGIN_REDIRECT_PATH, login_redirect_url, origin_absolute_url


def test_origin_absolute_url_bypasses_nicegui_mount_prefix(monkeypatch):
    from apps.web.config import settings

    monkeypatch.setattr(settings, "public_base_url", "https://resumebild.5432wire.com")
    url = origin_absolute_url(LOGIN_REDIRECT_PATH)
    assert url == "https://resumebild.5432wire.com/api/v1/auth/login-redirect"
    assert "/app/api/" not in url
    assert not url.startswith("/")


def test_login_redirect_url_is_scheme_qualified(monkeypatch):
    from apps.web.config import settings

    monkeypatch.setattr(settings, "public_base_url", "https://resumebild.5432wire.com")
    url = login_redirect_url()
    assert url.startswith("https://")
    assert url.endswith("/api/v1/auth/login-redirect")
    assert "/app/" not in url


def test_origin_absolute_url_uses_request_origin():
    from apps.web.ui import auth_guard

    class _Url:
        scheme = "https"
        netloc = "resumebild.5432wire.com"

    class _Request:
        url = _Url()

    token = auth_guard.request_contextvar.set(_Request())
    try:
        url = origin_absolute_url("/api/v1/auth/login-redirect")
        assert url == "https://resumebild.5432wire.com/api/v1/auth/login-redirect"
    finally:
        auth_guard.request_contextvar.reset(token)
