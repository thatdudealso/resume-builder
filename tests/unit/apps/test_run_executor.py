from __future__ import annotations

import pytest

from apps.web.services.run_executor import execute_run
from packages.core.security.jwt import register_user
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_execute_run_completes(session, monkeypatch):
    user = await register_user(session, "run@test.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="SUMMARY\nEngineer\nEXPERIENCE\nPython dev 2020-2022.",
    )
    session.add(resume)
    await session.flush()
    from packages.db.models.agent_run import AgentRun

    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="Python developer required " * 5,
        is_free_trial_run=True,
    )
    session.add(run)
    await session.commit()

    async def fake_run_agent(initial, llm_complete):
        return {
            "final_output": {"plain_text": "Tailored resume output."},
            "preview_text": "Tailored resume output.",
            "ats_score_before": 10.0,
            "ats_score_after": 80.0,
            "validation_passed": True,
        }

    monkeypatch.setattr("apps.web.services.run_executor.run_agent", fake_run_agent)
    await execute_run(session, run.id)
    await session.refresh(run)
    assert run.status == "completed"
