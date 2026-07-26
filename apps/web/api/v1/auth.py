from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from apps.web.dependencies import get_current_user, get_db
from packages.core.security.jwt import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    hash_ip,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from packages.db.models.device_session import DeviceSession
from packages.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.jwt_access_expire_minutes * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.jwt_refresh_expire_days * 86400,
    )


async def _upsert_device(
    session: AsyncSession,
    user_id: UUID,
    request: Request,
) -> None:
    fingerprint = request.headers.get("X-Device-Fingerprint", "unknown")
    ip_hash = hash_ip(request.client.host if request.client else "unknown")
    result = await session.execute(
        select(DeviceSession).where(
            DeviceSession.user_id == user_id,
            DeviceSession.device_fingerprint == fingerprint,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.last_seen_at = datetime.now(UTC)
        row.ip_hash = ip_hash
    else:
        session.add(
            DeviceSession(
                user_id=user_id,
                device_fingerprint=fingerprint,
                ip_hash=ip_hash,
                user_agent=request.headers.get("User-Agent"),
            )
        )


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    existing = await session.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await register_user(session, body.email, body.password)
    await _upsert_device(session, user.id, request)
    access = create_access_token(user.id)
    refresh = await create_refresh_token(session, user.id)
    await session.commit()
    _set_auth_cookies(response, access, refresh)
    return {"user_id": str(user.id), "email": user.email}


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(session, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await _upsert_device(session, user.id, request)
    access = create_access_token(user.id)
    refresh = await create_refresh_token(session, user.id)
    await session.commit()
    _set_auth_cookies(response, access, refresh)
    return {"user_id": str(user.id), "email": user.email}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    rotated = await rotate_refresh_token(session, refresh_token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access, refresh = rotated
    await session.commit()
    _set_auth_cookies(response, access, refresh)
    return {"ok": True}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await revoke_refresh_token(session, refresh_token)
        await session.commit()
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    from packages.core.access.service import AccessService

    snap = await AccessService(session).get_snapshot(user.id)
    return {
        "user": {"id": str(user.id), "email": user.email},
        "free_trial_used": snap.free_trial_used,
        "can_upload": snap.can_upload,
    }
