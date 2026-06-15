from __future__ import annotations

import pytest

from apps.web.services.run_executor import execute_run
from packages.core.security.jwt import register_user


@pytest.mark.asyncio
async def test_execute_run_missing_resume(session):
    user = await register_user(session, "missing@test.com", "password123")
    await session.flush()
    from uuid import uuid4
    from packages.db.models.agent_run import AgentRun

    run = AgentRun(
        user_id=user.id,
        master_resume_id=uuid4(),
        jd_text="jd " * 10,
    )
    session.add(run)
    await session.commit()
    await execute_run(session, run.id)
    await session.refresh(run)
    assert run.status == "failed"


@pytest.mark.asyncio
async def test_construct_event_stub(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_webhook_secret", "whsec_test")
    from packages.integrations import stripe_client

    def fake_construct(payload, sig, secret):
        assert secret == "whsec_test"
        return {"id": "evt", "type": "test"}

    monkeypatch.setattr(stripe_client.stripe.Webhook, "construct_event", fake_construct)
    event = stripe_client.construct_event(b"{}", "sig")
    assert event["id"] == "evt"
