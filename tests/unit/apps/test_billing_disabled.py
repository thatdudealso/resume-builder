from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.web.api.v1.billing import (
    CryptoInvoiceRequest,
    StripeCheckoutRequest,
    billing_status,
    crypto_invoice,
    stripe_checkout,
    stripe_verify,
)
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


def _disabled_settings(**overrides):
    return SimpleNamespace(
        payments_enabled=False,
        run_unlock_price_usd=3.99,
        support_url="",
        **overrides,
    )


async def _make_user_and_run(session, email):
    user = await register_user(session, email, "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id, master_resume_id=resume.id, jd_text="jd " * 10, output_locked=True
    )
    session.add(run)
    await session.commit()
    return user, run


@pytest.mark.asyncio
async def test_stripe_checkout_503_when_disabled(session, monkeypatch):
    user, run = await _make_user_and_run(session, "disabled-checkout@test.com")
    monkeypatch.setattr("apps.web.api.v1.billing.settings", _disabled_settings())

    with pytest.raises(HTTPException) as ei:
        await stripe_checkout(StripeCheckoutRequest(run_id=run.id), user=user, session=session)

    assert ei.value.status_code == 503
    assert ei.value.detail == "Payments are disabled on this server."


@pytest.mark.asyncio
async def test_stripe_verify_503_when_disabled(session, monkeypatch):
    user, run = await _make_user_and_run(session, "disabled-verify@test.com")
    monkeypatch.setattr("apps.web.api.v1.billing.settings", _disabled_settings())

    with pytest.raises(HTTPException) as ei:
        await stripe_verify(StripeCheckoutRequest(run_id=run.id), user=user, session=session)

    assert ei.value.status_code == 503
    assert ei.value.detail == "Payments are disabled on this server."


@pytest.mark.asyncio
async def test_crypto_invoice_503_when_disabled(session, monkeypatch):
    user, run = await _make_user_and_run(session, "disabled-crypto@test.com")
    monkeypatch.setattr("apps.web.api.v1.billing.settings", _disabled_settings())

    with pytest.raises(HTTPException) as ei:
        await crypto_invoice(
            CryptoInvoiceRequest(run_id=run.id, pay_currency="btc"), user=user, session=session
        )

    assert ei.value.status_code == 503
    assert ei.value.detail == "Payments are disabled on this server."


@pytest.mark.asyncio
async def test_billing_status_reports_flag(session, monkeypatch):
    user, _run = await _make_user_and_run(session, "disabled-status@test.com")
    monkeypatch.setattr("apps.web.api.v1.billing.settings", _disabled_settings())

    body = await billing_status(user=user, session=session)

    assert body["payments_enabled"] is False
    assert "support_url" in body
