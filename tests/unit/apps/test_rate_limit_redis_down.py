from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from apps.web.middleware.rate_limit import RateLimitMiddleware, reset_memory_rate_limits


@pytest.mark.asyncio
async def test_rate_limit_falls_back_when_redis_down(monkeypatch):
    reset_memory_rate_limits()

    async def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("apps.web.middleware.rate_limit.get_redis", boom)
    monkeypatch.setattr("apps.web.middleware.rate_limit.settings.env", "production")
    mw = RateLimitMiddleware(app=lambda s, r, send: None)

    async def call_next(request):
        return Response("ok")

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/runs",
        "headers": [],
        "client": ("203.0.113.9", 1234),
    }
    request = Request(scope)
    # Under the previous Redis-hard-fail behavior this returned 503. With the
    # in-memory fallback, run creation remains available.
    for _ in range(5):
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200
    blocked = await mw.dispatch(request, call_next)
    assert blocked.status_code == 429
