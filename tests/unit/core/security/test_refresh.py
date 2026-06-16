from __future__ import annotations

import pytest

from packages.core.security.jwt import (
    create_refresh_token,
    register_user,
    rotate_refresh_token,
)


@pytest.mark.asyncio
async def test_refresh_rotation(session):
    user = await register_user(session, "rot@test.com", "password123")
    await session.flush()
    refresh = await create_refresh_token(session, user.id)
    await session.commit()
    rotated = await rotate_refresh_token(session, refresh)
    assert rotated is not None
    access, new_refresh = rotated
    assert access
    assert new_refresh


@pytest.mark.asyncio
async def test_invalid_refresh(session):
    result = await rotate_refresh_token(session, "invalid-token")
    assert result is None
