from __future__ import annotations

import pytest

from packages.core.access.service import AccessService
from packages.core.security.jwt import register_user
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_upload_limit_by_resume_count(session):
    user = await register_user(session, "count@test.com", "password123")
    await session.flush()
    access = AccessService(session)
    assert await access.can_upload_resume(user.id) is True
    session.add(
        MasterResume(
            user_id=user.id,
            filename="a.pdf",
            s3_key="k",
            raw_text="text " * 20,
        )
    )
    await session.flush()
    assert await access.can_upload_resume(user.id) is False
