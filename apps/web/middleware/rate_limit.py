from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from apps.web.config import settings
from apps.web.dependencies import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    LIMITS = {
        "auth_register": (3, 86400),
        "auth_login": (10, 3600),
        "agent_run_create": (5, 3600),
        "billing_checkout": (10, 3600),
        "webhook": (1000, 60),
        "api_general": (100, 60),
    }

    def _endpoint_class(self, request: Request) -> str:
        path = request.url.path
        if path.endswith("/auth/register"):
            return "auth_register"
        if path.endswith("/auth/login"):
            return "auth_login"
        if path.endswith("/runs") and request.method == "POST":
            return "agent_run_create"
        if request.method == "POST" and (
            path.endswith("/billing/stripe/checkout") or path.endswith("/billing/crypto/invoice")
        ):
            return "billing_checkout"
        if "/webhooks/" in path:
            return "webhook"
        return "api_general"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if settings.env == "local":
            client_ip = request.client.host if request.client else ""
            if client_ip in {"127.0.0.1", "::1"}:
                response = await call_next(request)
                response.headers["X-RateLimit-Bypass"] = "local-loopback"
                return response

        endpoint_class = self._endpoint_class(request)
        limit, window = self.LIMITS.get(endpoint_class, (100, 60))
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{endpoint_class}:{client_ip}:{int(time.time()) // window}"

        try:
            r = await get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window)
            if count > limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                )
        except Exception:
            if endpoint_class == "agent_run_create":
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "Rate limiter unavailable"},
                )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response
