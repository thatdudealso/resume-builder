from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from apps.web.middleware.rate_limit import RateLimitMiddleware


@pytest.mark.asyncio
async def test_rate_limit_billing_status_not_checkout_limited(monkeypatch):
    counts: dict[str, int] = {}

    class FakeRedis:
        async def incr(self, key):
            counts[key] = counts.get(key, 0) + 1
            return counts[key]

        async def expire(self, key, ttl):
            return True

    async def fake_redis():
        return FakeRedis()

    monkeypatch.setattr("apps.web.middleware.rate_limit.get_redis", fake_redis)
    monkeypatch.setattr("apps.web.middleware.rate_limit.settings.env", "production")
    mw = RateLimitMiddleware(app=lambda s, r, send: None)

    async def call_next(request):
        return Response("ok")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/billing/status",
        "headers": [],
        "client": ("203.0.113.1", 1234),
    }
    request = Request(scope)
    for _ in range(15):
        response = await mw.dispatch(request, call_next)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_allows_requests(monkeypatch):
    class FakeRedis:
        async def incr(self, key):
            return 1

        async def expire(self, key, ttl):
            return True

    async def fake_redis():
        return FakeRedis()

    monkeypatch.setattr("apps.web.middleware.rate_limit.get_redis", fake_redis)
    mw = RateLimitMiddleware(app=lambda s, r, send: None)

    async def call_next(request):
        return Response("ok")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/me",
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }
    request = Request(scope)
    response = await mw.dispatch(request, call_next)
    assert response.status_code == 200
