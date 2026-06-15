from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable

import httpx
from nicegui import app as nicegui_app, ui


def _base_url() -> str:
    request = nicegui_app.storage.request  # type: ignore[attr-defined]
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "http://127.0.0.1:8000"


def _request_cookies() -> httpx.Cookies:
    request = nicegui_app.storage.request  # type: ignore[attr-defined]
    if request is None:
        return httpx.Cookies()
    return httpx.Cookies(request.cookies)


@asynccontextmanager
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=_base_url(),
        cookies=_request_cookies(),
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        yield client


def require_auth(page_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(page_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        request = nicegui_app.storage.request  # type: ignore[attr-defined]
        if request is None:
            ui.navigate.to("/app/login")
            return None
        if not request.cookies.get("access_token"):
            ui.navigate.to("/app/login")
            return None
        return page_func(*args, **kwargs)

    return wrapper
