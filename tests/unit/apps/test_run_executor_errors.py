from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from apps.web.services.run_executor import execute_run
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_execute_run_missing_resume(session, monkeypatch):
    """execute_run marks run as failed when the referenced resume is not found.

    We cannot insert an AgentRun with a non-existent master_resume_id on
    PostgreSQL (FK constraint). Instead we create a real resume, create the
    run referencing it, then patch session.get to return None for MasterResume
    to simulate the "resume deleted after run was queued" scenario.
    """
    user = await register_user(session, "missing@test.com", "password123")
    await session.flush()

    resume = MasterResume(
        user_id=user.id,
        filename="r.txt",
        s3_key="k",
        raw_text="dummy",
    )
    session.add(resume)
    await session.flush()

    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
    )
    session.add(run)
    await session.commit()

    original_get = session.get

    async def patched_get(model, pk, **kwargs):
        if model is MasterResume:
            return None
        return await original_get(model, pk, **kwargs)

    session.get = patched_get  # type: ignore[method-assign]

    @asynccontextmanager
    async def fake_get_checkpointer(database_url):
        yield AsyncMock()

    monkeypatch.setattr("apps.web.services.run_executor.get_checkpointer", fake_get_checkpointer)

    await execute_run(session, run.id)
    await session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Resume not found"


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
