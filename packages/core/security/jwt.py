from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from packages.core.security.passwords import hash_password, verify_password
from packages.db.models.refresh_token import RefreshToken
from packages.db.models.user import User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
ALGORITHM = "HS256"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}:{settings.jwt_secret}".encode()).hexdigest()


def create_access_token(user_id: UUID) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "exp": expire},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


async def create_refresh_token(session: AsyncSession, user_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires,
        )
    )
    await session.flush()
    return token


async def decode_access_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[str, str] | None:
    token_hash = hash_token(token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    await session.execute(
        update(RefreshToken).where(RefreshToken.id == row.id).values(revoked_at=datetime.now(UTC))
    )
    access = create_access_token(row.user_id)
    refresh = await create_refresh_token(session, row.user_id)
    return access, refresh


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    token_hash = hash_token(token)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked_at=datetime.now(UTC))
    )


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
