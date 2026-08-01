from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from apps.web.dependencies import get_current_user, get_db, get_or_create_cognito_user
from packages.core.security.cognito import decode_cognito_jwt
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


class CognitoExchangeRequest(BaseModel):
    id_token: str = Field(min_length=20)


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


def _local_auth_allowed(request: Request) -> bool:
    if settings.cognito_enabled and settings.env == "production":
        return False
    client_host = request.client.host if request.client else ""
    host_header = (request.headers.get("host") or "").lower()
    is_local = client_host in {"127.0.0.1", "::1", "localhost"} or host_header.startswith(
        ("localhost", "127.0.0.1")
    )
    return settings.env != "production" or is_local


def is_allowed_return_url(url: str) -> bool:
    """Validate an absolute return URL against the configured allowlist hosts."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"}:
        return False
    if parts.username or parts.password:
        return False
    if parts.fragment:
        return False
    origin = f"{parts.scheme}://{parts.netloc}".rstrip("/")
    return origin in settings.auth_return_allowlist_hosts


def build_login_redirect_url(return_url: str) -> str:
    if not is_allowed_return_url(return_url):
        raise ValueError("return_url is not allowlisted")
    base = settings.auth_login_url.strip()
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["return_url"] = return_url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


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


@router.get("/login-redirect")
async def login_redirect(request: Request) -> RedirectResponse:
    """Send unauthenticated visitors to 5432wire login with a validated return URL."""
    callback = f"{settings.public_base_url.rstrip('/')}/auth/callback"
    if not is_allowed_return_url(callback):
        raise HTTPException(status_code=500, detail="Public callback URL is not allowlisted")
    try:
        target = build_login_redirect_url(callback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=target, status_code=302)


@router.post("/cognito/exchange")
async def cognito_exchange(
    body: CognitoExchangeRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    if not settings.cognito_enabled:
        raise HTTPException(status_code=404, detail="Cognito auth is not configured")
    payload = decode_cognito_jwt(body.id_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid Cognito token")
    user = await get_or_create_cognito_user(session, payload)
    access = create_access_token(user.id)
    refresh = await create_refresh_token(session, user.id)
    await session.commit()
    _set_auth_cookies(response, access, refresh)
    return {"user_id": str(user.id), "email": user.email}


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    if not _local_auth_allowed(request):
        raise HTTPException(status_code=404, detail="Not found")
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
    if not _local_auth_allowed(request):
        raise HTTPException(status_code=404, detail="Not found")
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
