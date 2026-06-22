from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.web.services.stripe_billing import (
    _payment_for_session,
    _session_metadata,
    _stripe_session_paid,
    confirm_stripe_payment,
    sync_stripe_payment_for_run,
)
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


def test_session_metadata_from_dict():
    assert _session_metadata(SimpleNamespace(metadata={"run_id": "abc", "user_id": "xyz"})) == {
        "run_id": "abc",
        "user_id": "xyz",
    }


def test_session_metadata_from_stripe_object():
    class Meta:
        def to_dict(self):
            return {"run_id": "1"}

    assert _session_metadata(SimpleNamespace(metadata=Meta())) == {"run_id": "1"}


def test_session_metadata_from_keys():
    class Meta:
        def keys(self):
            return ["run_id"]

        def __getitem__(self, key: str) -> str:
            return "run-1"

    assert _session_metadata(SimpleNamespace(metadata=Meta())) == {"run_id": "run-1"}


def test_stripe_session_paid():
    assert _stripe_session_paid(SimpleNamespace(payment_status="paid")) is True
    assert _stripe_session_paid(SimpleNamespace(payment_status="unpaid")) is False


def test_session_metadata_empty():
    assert _session_metadata(SimpleNamespace(metadata=None)) == {}


def test_session_metadata_without_keys_returns_empty():
    assert _session_metadata(SimpleNamespace(metadata=object())) == {}


@pytest.mark.asyncio
async def test_payment_for_session_reuses_pending(session):
    user = await register_user(session, "stripe-pending@test.com", "password123")
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
    session.add(run)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="pending_old",
        idempotency_key="pending-session",
        amount_usd=Decimal("3.99"),
        status="pending",
    )
    session.add(payment)
    await session.commit()

    found = await _payment_for_session(
        session,
        user_id=user.id,
        run_id=run.id,
        session_id="cs_new",
    )
    assert found.id == payment.id


@pytest.mark.asyncio
async def test_payment_for_session_reuses_existing(session):
    user = await register_user(session, "stripe-existing@test.com", "password123")
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
    session.add(run)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="cs_existing",
        idempotency_key="existing-session",
        amount_usd=Decimal("3.99"),
        status="pending",
    )
    session.add(payment)
    await session.commit()

    found = await _payment_for_session(
        session,
        user_id=user.id,
        run_id=run.id,
        session_id="cs_existing",
    )
    assert found.id == payment.id


@pytest.mark.asyncio
async def test_sync_returns_false_when_stripe_not_configured(session, monkeypatch):
    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: False)
    ok = await sync_stripe_payment_for_run(session, user_id=uuid4(), run_id=uuid4())
    assert ok is False


@pytest.mark.asyncio
async def test_sync_returns_true_when_run_already_unlocked(session, monkeypatch):
    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: True)
    user = await register_user(session, "stripe-unlocked@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
    )
    session.add(run)
    await session.commit()

    ok = await sync_stripe_payment_for_run(session, user_id=user.id, run_id=run.id)
    assert ok is True


@pytest.mark.asyncio
async def test_sync_unlocks_from_pending_checkout_session(session, monkeypatch):
    user = await register_user(session, "stripe-sync@test.com", "password123")
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
    session.add(run)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="cs_test_pending",
        idempotency_key="sync-pending",
        amount_usd=Decimal("3.99"),
        status="pending",
    )
    session.add(payment)
    await session.commit()

    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: True)
    monkeypatch.setattr(
        "apps.web.services.stripe_billing.stripe.checkout.Session.retrieve",
        lambda session_id: SimpleNamespace(payment_status="paid"),
    )
    monkeypatch.setattr(
        "apps.web.services.stripe_billing.stripe.checkout.Session.list",
        lambda **kwargs: SimpleNamespace(auto_paging_iter=lambda: iter([])),
    )

    ok = await sync_stripe_payment_for_run(session, user_id=user.id, run_id=run.id)
    assert ok is True

    refreshed = await session.get(AgentRun, run.id)
    assert refreshed is not None
    assert refreshed.output_locked is False


@pytest.mark.asyncio
async def test_sync_unlocks_from_stripe_session_list(session, monkeypatch):
    user = await register_user(session, "stripe-list@test.com", "password123")
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
    session.add(run)
    await session.commit()

    stripe_session = SimpleNamespace(
        id="cs_test_list",
        payment_status="paid",
        metadata={"run_id": str(run.id), "user_id": str(user.id)},
    )
    listed = SimpleNamespace(auto_paging_iter=lambda: iter([stripe_session]))

    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: True)
    monkeypatch.setattr(
        "apps.web.services.stripe_billing.stripe.checkout.Session.list",
        lambda **kwargs: listed,
    )

    ok = await sync_stripe_payment_for_run(session, user_id=user.id, run_id=run.id)
    assert ok is True


@pytest.mark.asyncio
async def test_sync_unlocks_when_confirmed_payment_exists(session, monkeypatch):
    user = await register_user(session, "stripe-confirmed@test.com", "password123")
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
    session.add(run)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="cs_confirmed_existing",
        idempotency_key="confirmed-existing",
        amount_usd=Decimal("3.99"),
        status="confirmed",
    )
    session.add(payment)
    await session.commit()

    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: True)

    ok = await sync_stripe_payment_for_run(session, user_id=user.id, run_id=run.id)
    assert ok is True

    refreshed = await session.get(AgentRun, run.id)
    assert refreshed is not None
    assert refreshed.output_locked is False


@pytest.mark.asyncio
async def test_sync_returns_false_for_missing_run(session, monkeypatch):
    monkeypatch.setattr("apps.web.services.stripe_billing.is_stripe_configured", lambda: True)
    ok = await sync_stripe_payment_for_run(session, user_id=uuid4(), run_id=uuid4())
    assert ok is False


@pytest.mark.asyncio
async def test_confirm_stripe_payment(session):
    user = await register_user(session, "stripe-confirm@test.com", "password123")
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
    session.add(run)
    await session.flush()
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="pending_old",
        idempotency_key="confirm-test",
        amount_usd=Decimal("3.99"),
        status="pending",
    )
    session.add(payment)
    await session.commit()

    await confirm_stripe_payment(
        session,
        payment=payment,
        run_id=run.id,
        provider_payment_id="cs_confirmed",
    )

    refreshed = await session.get(AgentRun, run.id)
    assert refreshed is not None
    assert refreshed.output_locked is False
    assert payment.status == "confirmed"
