from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

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
        llm_provider="huggingface",
        is_free_trial_run=True,
    )
    session.add(run)
    await session.commit()

    async def fake_run_agent(initial, agent_service, *, on_progress=None, checkpointer=None):
        return {
            "final_output": {
                "plain_text": "Tailored resume output.",
                "variants": {"balanced": {"plain_text": "Tailored resume output."}},
                "match_score": {"previous_overall": 40.0, "current_overall": 75.0},
            },
            "preview_text": "Tailored resume output.",
            "match_score_before": {"overall": 40.0},
            "match_score_after": {"overall": 75.0},
            "ats_score_before": 40.0,
            "ats_score_after": 75.0,
            "validation_passed": True,
        }

    mock_checkpointer = AsyncMock()

    @asynccontextmanager
    async def fake_get_checkpointer(database_url):
        yield mock_checkpointer

    monkeypatch.setattr("apps.web.services.run_executor.run_agent", fake_run_agent)
    monkeypatch.setattr("apps.web.services.run_executor.get_checkpointer", fake_get_checkpointer)
    await execute_run(session, run.id)
    await session.refresh(run)
    assert run.status == "completed"
    assert float(run.ats_score_before) == 40.0
    assert float(run.ats_score_after) == 75.0
