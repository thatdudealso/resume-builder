from __future__ import annotations

import time
from typing import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from apps.web.dependencies import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    LIMITS = {
        "auth_register": (3, 86400),
        "auth_login": (10, 3600),
        "agent_run_create": (5, 3600),
        "billing_checkout": (10, 3600),
        "api_general": (100, 60),
    }

    async def dispatch(self, request: Request, call_next: Callable):
        endpoint_class = "api_general"
        path = request.url.path
        if path.endswith("/auth/register"):
            endpoint_class = "auth_register"
        elif path.endswith("/auth/login"):
            endpoint_class = "auth_login"
        elif path.endswith("/runs") and request.method == "POST":
            endpoint_class = "agent_run_create"
        elif "/billing/" in path:
            endpoint_class = "billing_checkout"

        limit, window = self.LIMITS.get(endpoint_class, (100, 60))
        client_ip = request.client.host if request.client else "unknown"
        key = f"rl:{endpoint_class}:{client_ip}:{int(time.time()) // window}"

        try:
            r = await get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window)
            if count > limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        except HTTPException:
            raise
        except Exception:
            if endpoint_class == "agent_run_create":
                raise HTTPException(status_code=503, detail="Rate limiter unavailable")

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response
