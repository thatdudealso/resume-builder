from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from nicegui.storage import request_contextvar
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import _get_or_create_device_user_id
from packages.db.models.user import User
from packages.db.session import SessionLocal


@asynccontextmanager
async def request_user_session() -> AsyncIterator[tuple[AsyncSession, User]]:
    request = request_contextvar.get()
    if request is None:
        raise RuntimeError("No active request context for in-process API call")
    async with SessionLocal() as session:
        user_id = await _get_or_create_device_user_id(request, session)
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            raise RuntimeError("User inactive")
        yield session, user
