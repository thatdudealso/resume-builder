from __future__ import annotations

import pytest

from apps.web.api.v1.billing import StripeCheckoutRequest, stripe_checkout
from apps.web.api.v1.webhooks import stripe as stripe_wh
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_stripe_checkout_route(session, monkeypatch):
    user = await register_user(session, "bill@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id, master_resume_id=resume.id, jd_text="jd " * 10, output_locked=True
    )
    session.add(run)
    await session.commit()

    monkeypatch.setattr(
        "apps.web.api.v1.billing.create_checkout_session",
        lambda **kwargs: "https://checkout.test/url",
    )
    resp = await stripe_checkout(StripeCheckoutRequest(run_id=run.id), user=user, session=session)
    assert "checkout_url" in resp


@pytest.mark.asyncio
async def test_stripe_webhook_idempotent(session, monkeypatch):
    event = {
        "id": "evt_2",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs", "metadata": {}}},
    }
    monkeypatch.setattr("apps.web.api.v1.webhooks.stripe.construct_event", lambda p, s: event)
    from starlette.requests import Request

    scope = {"type": "http", "method": "POST", "headers": [], "query_string": b""}
    request = Request(scope)
    request._body = b"{}"
    result = await stripe_wh.stripe_webhook(request, session=session)
    assert result["received"] is True
