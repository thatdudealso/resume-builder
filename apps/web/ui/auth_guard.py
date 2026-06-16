from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

import httpx
from nicegui import ui
from nicegui.storage import request_contextvar


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
        return "nicegui-client"
    return request.cookies.get("rb_device_fingerprint", "nicegui-client")


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


def require_auth(page_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(page_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = request_contextvar.get()
        if request is None:
            ui.navigate.to("/login")
            return None
        if not request.cookies.get("access_token"):
            ui.navigate.to("/login")
            return None
        return page_func(*args, **kwargs)

    return wrapper
