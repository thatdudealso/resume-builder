from __future__ import annotations

from decimal import Decimal

import pytest

from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_free_trial_run_access(session):
    user = await register_user(session, "free@example.com", "password123")
    await session.flush()
    access = AccessService(session)
    decision = await access.can_start_run(user.id)
    assert decision.mode == RunAccessMode.FREE
    user.free_trial_used = True
    await session.flush()
    decision2 = await access.can_start_run(user.id)
    assert decision2.mode == RunAccessMode.LOCKED


@pytest.mark.asyncio
async def test_unlock_run(session):
    user = await register_user(session, "paid@example.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.pdf",
        s3_key="k",
        raw_text="text " * 20,
    )
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="job " * 10,
        output_locked=True,
    )
    payment = Payment(
        user_id=user.id,
        provider="stripe",
        provider_payment_id="pi_test",
        idempotency_key="key-1",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.flush()
    access = AccessService(session)
    await access.unlock_run(payment.id, run.id)
    await session.refresh(run)
    assert run.output_locked is False
    assert await access.can_view_output(user.id, run)
