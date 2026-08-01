from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from packages.core.security.jwt import ACCESS_COOKIE, decode_access_token, hash_ip
from packages.core.security.passwords import hash_password
from packages.db.models.device_session import DeviceSession
from packages.db.models.user import User
from packages.db.session import get_session

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def _request_fingerprint(request: Request) -> str | None:
    raw = request.headers.get("X-Device-Fingerprint") or request.cookies.get(
        "rb_device_fingerprint"
    )
    if not raw:
        return None
    fingerprint = raw.strip()
    if not fingerprint:
        return None
    if len(fingerprint) > 64:
        return f"fp-{hashlib.sha256(fingerprint.encode()).hexdigest()}"
    return fingerprint


async def _get_or_create_device_user_id(request: Request, session: AsyncSession) -> UUID:
    fingerprint = _request_fingerprint(request)
    if fingerprint is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    email = f"device-{digest}@resume-builder.local"
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        session.add(user)
        await session.flush()

    ip_hash = hash_ip(request.client.host if request.client else "unknown")
    existing_device = await session.execute(
        select(DeviceSession).where(
            DeviceSession.user_id == user.id,
            DeviceSession.device_fingerprint == fingerprint,
        )
    )
    device = existing_device.scalar_one_or_none()
    if device is None:
        session.add(
            DeviceSession(
                user_id=user.id,
                device_fingerprint=fingerprint,
                ip_hash=ip_hash,
                user_agent=request.headers.get("User-Agent"),
            )
        )
    else:
        device.ip_hash = ip_hash
        device.user_agent = request.headers.get("User-Agent")
    await session.commit()
    return user.id


async def get_or_create_cognito_user(session: AsyncSession, payload: dict[str, Any]) -> User:
    cognito_sub = str(payload["sub"])
    email_verified = payload.get("email_verified") is True
    claimed_email = str(payload.get("email") or "").lower()
    email = (
        claimed_email
        if email_verified and claimed_email
        else f"cognito-{cognito_sub}@resume-builder.local"
    )
    result = await session.execute(select(User).where(User.cognito_sub == cognito_sub))
    user = result.scalar_one_or_none()
    if user is not None:
        if email and user.email != email and not user.email.endswith("@resume-builder.local"):
            pass
        elif email and user.email.startswith("cognito-"):
            user.email = email
        return user

    if email_verified:
        by_email = await session.execute(select(User).where(User.email == email))
        existing = by_email.scalar_one_or_none()
        if existing is not None:
            existing.cognito_sub = cognito_sub
            return existing

    user = User(
        email=email,
        password_hash=None,
        cognito_sub=cognito_sub,
    )
    session.add(user)
    await session.flush()
    return user


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    return None


async def get_current_user_id(
    request: Request,
    session: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
) -> UUID:
    token = access_token or request.cookies.get(ACCESS_COOKIE) or _extract_bearer(request)

    if token:
        # Prefer ResumeBild session cookies / local JWTs.
        user_id = await decode_access_token(token)
        if user_id is not None:
            return user_id

        # Production Cognito hard-gate uses the exchange endpoint to mint
        # ResumeBild cookies. Do not accept raw Cognito bearer tokens here.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if settings.env == "production" or settings.cognito_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return await _get_or_create_device_user_id(request, session)


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user
