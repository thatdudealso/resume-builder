from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_crypto_webhook_unlocks(client, session, monkeypatch):
    user = await register_user(session, "crypto@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
    )
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="crypto",
        provider_payment_id="np_abc123",
        idempotency_key="ck1",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.commit()

    monkeypatch.setattr(
        "apps.web.api.v1.webhooks.crypto.verify_ipn_signature",
        lambda p, s: True,
    )
    payload = {"payment_id": "np_abc123", "payment_status": "finished"}
    resp = await client.post(
        "/api/v1/webhooks/crypto",
        content=json.dumps(payload),
        headers={"x-nowpayments-sig": "sig"},
    )
    assert resp.status_code == 200
