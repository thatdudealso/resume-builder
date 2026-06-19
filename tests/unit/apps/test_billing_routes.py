from __future__ import annotations

from decimal import Decimal

import pytest

from apps.web.api.v1.billing import StripeCheckoutRequest, stripe_checkout, stripe_verify
from apps.web.api.v1.webhooks import stripe as stripe_wh
from packages.core.access.service import AccessService
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume
from packages.integrations.stripe_client import StripeCheckoutResult


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
        lambda **kwargs: StripeCheckoutResult(
            url="https://checkout.test/url",
            session_id="cs_test_checkout",
        ),
    )
    resp = await stripe_checkout(StripeCheckoutRequest(run_id=run.id), user=user, session=session)
    assert "checkout_url" in resp
    assert resp["checkout_session_id"] == "cs_test_checkout"


@pytest.mark.asyncio
async def test_stripe_verify_endpoint(session, monkeypatch):
    user = await register_user(session, "verify@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id, master_resume_id=resume.id, jd_text="jd " * 10, output_locked=True
    )
    session.add(run)
    await session.commit()

    async def fake_sync(db_session, *, user_id, run_id):
        payment = Payment(
            user_id=user_id,
            run_id=run_id,
            provider="stripe",
            provider_payment_id="cs_test",
            idempotency_key="verify-test",
            amount_usd=Decimal("3.99"),
            status="pending",
        )
        db_session.add(payment)
        await db_session.flush()
        await AccessService(db_session).unlock_run(payment.id, run_id)
        await db_session.commit()
        return True

    monkeypatch.setattr("apps.web.api.v1.billing.is_stripe_configured", lambda: True)
    monkeypatch.setattr("apps.web.api.v1.billing.sync_stripe_payment_for_run", fake_sync)

    resp = await stripe_verify(StripeCheckoutRequest(run_id=run.id), user=user, session=session)
    assert resp["unlocked"] is True
    assert resp["output_locked"] is False


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
