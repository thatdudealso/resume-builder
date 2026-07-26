from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.web.config import settings

DEVICE_FINGERPRINT_COOKIE = "rb_device_fingerprint"


class DeviceFingerprintMiddleware(BaseHTTPMiddleware):
    """Set a stable device-fingerprint cookie on the first `/app` page load.

    Without this, the client-side JS that sets `rb_device_fingerprint` runs too
    late for the very first API call the page makes, so `/api/v1/auth/me` 401s
    on a brand new visitor. Setting the cookie here - on the response to the
    first `/app` GET - guarantees it is present for every subsequent request.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.method == "GET" and request.url.path.startswith("/app"):
            if not request.cookies.get(DEVICE_FINGERPRINT_COOKIE):
                token = f"srv-{secrets.token_hex(8)}"
                response.set_cookie(
                    DEVICE_FINGERPRINT_COOKIE,
                    token,
                    max_age=31536000,
                    samesite="lax",
                    path="/",
                    secure=settings.cookie_secure,
                )
        return response
