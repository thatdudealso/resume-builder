from __future__ import annotations

import pytest

from apps.web.config import settings
from apps.web.middleware.security_headers import SecurityHeadersMiddleware


@pytest.mark.asyncio
async def test_security_headers_added():
    mw = SecurityHeadersMiddleware(app=lambda scope, receive, send: None)

    async def call_next(request):
        from starlette.responses import Response

        return Response("ok")

    from starlette.requests import Request

    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    response = await mw.dispatch(request, call_next)
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_settings_cookie_secure():
    assert settings.cookie_secure is False or settings.env != "local"
