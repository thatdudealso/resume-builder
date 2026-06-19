from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apps.web.services.run_launcher import RunLaunchError, create_and_schedule_run, create_run_record
from packages.core.security.jwt import register_user
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_create_run_record_persists(session):
    user = await register_user(session, "launcher@test.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="SUMMARY\nEngineer\nEXPERIENCE\nPython dev 2020-2022.",
    )
    session.add(resume)
    await session.commit()

    result = await create_run_record(
        session,
        user,
        resume_id=resume.id,
        jd_text="Python developer required " * 5,
        llm_provider="huggingface",
        variant="balanced",
    )

    assert result["run_id"]
    assert result["llm_provider"] == "huggingface"


@pytest.mark.asyncio
async def test_create_and_schedule_run_schedules_background(session, monkeypatch):
    user = await register_user(session, "launcher-schedule@test.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="SUMMARY\nEngineer\nEXPERIENCE\nPython dev 2020-2022.",
    )
    session.add(resume)
    await session.commit()

    scheduled: list[str] = []

    def fake_create_task(coro):
        scheduled.append("task")
        coro.close()
        return AsyncMock()

    monkeypatch.setattr("apps.web.services.run_launcher.asyncio.create_task", fake_create_task)

    result = await create_and_schedule_run(
        session,
        user,
        resume_id=resume.id,
        jd_text="Python developer required " * 5,
        llm_provider="huggingface",
        variant="balanced",
    )

    assert result["run_id"]
    assert scheduled == ["task"]


@pytest.mark.asyncio
async def test_create_run_record_rejects_missing_resume(session):
    user = await register_user(session, "launcher-missing@test.com", "password123")
    await session.commit()

    with pytest.raises(RunLaunchError) as exc:
        await create_run_record(
            session,
            user,
            resume_id=user.id,
            jd_text="Python developer required " * 5,
            llm_provider="huggingface",
            variant="balanced",
        )

    assert exc.value.status_code == 404
