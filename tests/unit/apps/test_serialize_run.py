from __future__ import annotations

import pytest

from apps.web.api.v1.runs import _serialize_run
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_serialize_run_locked_without_view(session):
    user = await register_user(session, "ser@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
        final_output={"plain_text": "hidden"},
        preview_text="preview",
    )
    session.add(run)
    await session.flush()
    payload = _serialize_run(run, False)
    assert payload["final_output"] is None
    assert payload["preview_text"] == "preview"
    assert payload["master_resume_id"] == str(resume.id)
    assert payload["jd_text"] == run.jd_text
