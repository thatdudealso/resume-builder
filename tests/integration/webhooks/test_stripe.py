from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_stripe_webhook_unlocks_run(client, session, monkeypatch):
    user = await register_user(session, "stripe@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
        status="completed",
        final_output={"plain_text": "secret"},
    )
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="pending_x",
        idempotency_key="k1",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.commit()

    event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test",
                "metadata": {"user_id": str(user.id), "run_id": str(run.id)},
            }
        },
    }

    def mock_construct(payload, sig):
        return event

    monkeypatch.setattr(
        "apps.web.api.v1.webhooks.stripe.construct_event",
        mock_construct,
    )
    resp = await client.post(
        "/api/v1/webhooks/stripe",
        content=json.dumps(event),
        headers={"stripe-signature": "test"},
    )
    assert resp.status_code == 200
