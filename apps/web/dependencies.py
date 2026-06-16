from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncGenerator
from uuid import UUID

import redis.asyncio as redis
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.security.jwt import ACCESS_COOKIE, decode_access_token, hash_ip
from packages.core.security.passwords import hash_password
from packages.db.models.device_session import DeviceSession
from packages.db.models.user import User
from packages.db.session import get_session

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    from apps.web.config import settings

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


async def get_current_user_id(
    request: Request,
    session: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
) -> UUID:
    token = access_token
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return await _get_or_create_device_user_id(request, session)
    user_id = await decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user
