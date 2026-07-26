from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from apps.web.services.run_launcher import (
    RunLaunchError,
    create_and_schedule_run,
    create_run_record,
)
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
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
        llm_provider="openai",
        variant="balanced",
    )

    assert result["run_id"]
    assert result["llm_provider"] == "openai"


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
        llm_provider="openai",
        variant="balanced",
    )

    assert result["run_id"]
    assert scheduled == ["task"]


@pytest.mark.asyncio
async def test_create_run_record_uses_active_payment_window(session):
    user = await register_user(session, "launcher-paid-window@test.com", "password123")
    user.free_trial_used = True
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="SUMMARY\nEngineer\nEXPERIENCE\nPython dev 2020-2022.",
    )
    payment = Payment(
        user_id=user.id,
        provider="stripe",
        provider_payment_id="pi_launcher_window",
        idempotency_key="launcher-window",
        amount_usd=Decimal("3.99"),
        status="confirmed",
        confirmed_at=datetime.now(UTC),
    )
    session.add_all([resume, payment])
    await session.commit()

    result = await create_run_record(
        session,
        user,
        resume_id=resume.id,
        jd_text="Python developer required " * 5,
        llm_provider="openai",
        variant="balanced",
    )

    run = await session.get(AgentRun, UUID(str(result["run_id"])))
    assert result["output_locked"] is False
    assert run is not None
    assert run.is_free_trial_run is False
    assert run.payment_id == payment.id


@pytest.mark.asyncio
async def test_create_run_record_fails_closed_when_paid_without_active_payment(
    session, monkeypatch
):
    user = await register_user(session, "launcher-paid-missing@test.com", "password123")
    user.free_trial_used = True
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="SUMMARY\nEngineer\nEXPERIENCE\nPython dev 2020-2022.",
    )
    session.add(resume)
    await session.commit()

    from packages.core.schemas.access import RunAccessDecision, RunAccessMode

    async def fake_can_start_run(self, user_id):
        return RunAccessDecision(mode=RunAccessMode.PAID)

    async def fake_get_active_payment(self, user_id):
        return None

    monkeypatch.setattr(
        "apps.web.services.run_launcher.AccessService.can_start_run",
        fake_can_start_run,
    )
    monkeypatch.setattr(
        "apps.web.services.run_launcher.AccessService.get_active_payment",
        fake_get_active_payment,
    )

    result = await create_run_record(
        session,
        user,
        resume_id=resume.id,
        jd_text="Python developer required " * 5,
        llm_provider="openai",
        variant="balanced",
    )

    run = await session.get(AgentRun, UUID(str(result["run_id"])))
    assert result["output_locked"] is True
    assert run is not None
    assert run.payment_id is None
    assert run.is_free_trial_run is False


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
            llm_provider="openai",
            variant="balanced",
        )

    assert exc.value.status_code == 404
