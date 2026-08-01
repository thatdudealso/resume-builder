from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from apps.web.api.router import api_router, health_router
from apps.web.auth_callback import AUTH_CALLBACK_HTML
from apps.web.config import settings
from apps.web.middleware.device_fingerprint import DeviceFingerprintMiddleware
from apps.web.middleware.rate_limit import RateLimitMiddleware
from apps.web.middleware.security_headers import SecurityHeadersMiddleware
from apps.web.services.s3_bootstrap import ensure_bucket_exists
from packages.agent.checkpointer import ensure_checkpointer_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.env not in ("test",):
        await ensure_checkpointer_schema(settings.database_url)
        await ensure_bucket_exists()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Resume Builder", version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(DeviceFingerprintMiddleware)
    app.include_router(api_router)
    app.include_router(health_router)

    @app.get("/auth/callback", response_class=HTMLResponse, include_in_schema=False)
    async def auth_callback_page() -> HTMLResponse:
        return HTMLResponse(AUTH_CALLBACK_HTML)

    return app


app = create_app()

if settings.env not in ("test",):
    from nicegui import ui

    from apps.web.ui import app as ui_pages

    ui_pages.mount_ui()
    ui.run_with(app, mount_path="/app", title="Resume Builder", storage_secret=settings.jwt_secret)
