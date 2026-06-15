from __future__ import annotations

import pytest

from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.core.security.jwt import register_user


@pytest.mark.asyncio
async def test_access_blocked_unknown_user(session):
    from uuid import uuid4

    access = AccessService(session)
    decision = await access.can_start_run(uuid4())
    assert decision.mode == RunAccessMode.BLOCKED


@pytest.mark.asyncio
async def test_get_snapshot(session):
    user = await register_user(session, "snap@test.com", "password123")
    await session.flush()
    snap = await AccessService(session).get_snapshot(user.id)
    assert snap.user_id == user.id
