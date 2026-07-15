from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.web.api.router import api_router, health_router
from apps.web.config import settings
from apps.web.middleware.device_fingerprint import DeviceFingerprintMiddleware
from apps.web.middleware.rate_limit import RateLimitMiddleware
from apps.web.middleware.security_headers import SecurityHeadersMiddleware
from packages.agent.checkpointer import ensure_checkpointer_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.env not in ("test",):
        await ensure_checkpointer_schema(settings.database_url)
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
    return app


app = create_app()

if settings.env not in ("test",):
    from nicegui import ui

    from apps.web.ui import app as ui_pages

    ui_pages.mount_ui()
    ui.run_with(app, mount_path="/app", title="Resume Builder", storage_secret=settings.jwt_secret)
