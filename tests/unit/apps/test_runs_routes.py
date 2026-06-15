from __future__ import annotations

import pytest

from apps.web.api.v1.runs import unlock_run
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_unlock_endpoint_already_unlocked(session):
    user = await register_user(session, "unlock@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
    )
    session.add(run)
    await session.commit()
    result = await unlock_run(run.id, user=user, session=session)
    assert result.get("already_unlocked") is True
