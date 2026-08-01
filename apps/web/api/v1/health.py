from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from apps.web.dependencies import get_db, get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)):
    db_ok = True
    redis_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        r = await get_redis()
        await r.ping()
    except Exception:
        redis_ok = False
    # Redis is optional (in-memory rate-limit fallback). DB is required for readiness.
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok}


@router.get("/ready")
async def ready():
    return {"ready": True}


@router.get("/deployments/latest")
async def latest_deployment():
    return {
        "version": settings.app_version,
        "deployed_at": settings.deployed_at or None,
        "env": settings.deploy_env,
    }
