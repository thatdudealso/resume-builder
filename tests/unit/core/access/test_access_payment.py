from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from packages.core.access.service import AccessService
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_can_view_via_confirmed_payment_id(session):
    user = await register_user(session, "confirmed@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        provider="stripe",
        provider_payment_id="pi_confirmed",
        idempotency_key="idem-confirmed",
        amount_usd=Decimal("9.99"),
        status="confirmed",
    )
    session.add(payment)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
        payment_id=payment.id,
        status="completed",
    )
    session.add(run)
    await session.flush()
    access = AccessService(session)
    assert await access.can_view_output(user.id, run) is True
    assert await access.can_view_output(uuid4(), run) is False


@pytest.mark.asyncio
async def test_upload_allowed_after_confirmed_payment(session):
    user = await register_user(session, "paidup@test.com", "password123")
    await session.flush()
    session.add(
        Payment(
            user_id=user.id,
            provider="stripe",
            provider_payment_id="pi_paid",
            idempotency_key="idem-paid",
            amount_usd=Decimal("9.99"),
            status="confirmed",
        )
    )
    session.add(
        MasterResume(user_id=user.id, filename="a.pdf", s3_key="k", raw_text="text " * 20)
    )
    await session.flush()
    access = AccessService(session)
    assert await access.can_upload_resume(user.id) is True


@pytest.mark.asyncio
async def test_unlock_run_missing_entities(session):
    access = AccessService(session)
    await access.unlock_run(uuid4(), uuid4())
