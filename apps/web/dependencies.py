from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

import redis.asyncio as redis
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.security.jwt import ACCESS_COOKIE, decode_access_token
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


async def get_current_user_id(
    request: Request,
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
) -> UUID:
    token = access_token
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
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
