from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from nicegui.storage import request_contextvar

from apps.web.config import settings

# FastAPI Cognito handoff endpoint (site root). Must NOT be mount-relative.
LOGIN_REDIRECT_PATH = "/api/v1/auth/login-redirect"


def origin_absolute_url(path: str) -> str:
    """Return a scheme-qualified URL at the site origin.

    NiceGUI's browser ``open`` handler prefixes every leading-``/`` path with the
    UI mount (``/app``). Passing ``/api/v1/...`` therefore navigates to
    ``/app/api/v1/...`` and 404s. Absolute ``https://host/api/...`` URLs bypass
    that rewrite.
    """
    if path.startswith(("http://", "https://")):
        return path
    normalized = path if path.startswith("/") else f"/{path}"
    request = request_contextvar.get()
    if request is not None:
        return f"{request.url.scheme}://{request.url.netloc}{normalized}"
    return f"{settings.public_base_url.rstrip('/')}{normalized}"


def login_redirect_url() -> str:
    return origin_absolute_url(LOGIN_REDIRECT_PATH)


def _base_url() -> str:
    request = request_contextvar.get()
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "http://127.0.0.1:8000"


def _request_cookies() -> httpx.Cookies:
    request = request_contextvar.get()
    if request is None:
        return httpx.Cookies()
    return httpx.Cookies(request.cookies)


def _request_fingerprint() -> str:
    request = request_contextvar.get()
    if request is None:
        return ""
    return request.cookies.get("rb_device_fingerprint", "")


@asynccontextmanager
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=_base_url(),
        cookies=_request_cookies(),
        headers={"X-Device-Fingerprint": _request_fingerprint()},
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        yield client
