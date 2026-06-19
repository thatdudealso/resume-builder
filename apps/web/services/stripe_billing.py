from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from packages.core.access.service import AccessService
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.integrations.stripe_client import is_stripe_configured


async def confirm_stripe_payment(
    session: AsyncSession,
    *,
    payment: Payment,
    run_id: UUID,
    provider_payment_id: str,
) -> None:
    payment.status = "confirmed"
    payment.confirmed_at = datetime.now(UTC)
    payment.provider_payment_id = provider_payment_id
    await AccessService(session).unlock_run(payment.id, run_id)
    await session.commit()


async def _payment_for_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    run_id: UUID,
    session_id: str,
) -> Payment:
    existing = await session.execute(
        select(Payment).where(
            Payment.provider == "stripe",
            Payment.provider_payment_id == session_id,
        )
    )
    payment = existing.scalar_one_or_none()
    if payment is not None:
        return payment

    pending = await session.execute(
        select(Payment)
        .where(
            Payment.run_id == run_id,
            Payment.user_id == user_id,
            Payment.provider == "stripe",
            Payment.status == "pending",
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    payment = pending.scalar_one_or_none()
    if payment is not None:
        return payment

    payment = Payment(
        user_id=user_id,
        run_id=run_id,
        provider="stripe",
        provider_payment_id=session_id,
        idempotency_key=f"stripe-sync-{session_id}",
        amount_usd=settings.run_unlock_price_usd,
        status="pending",
    )
    session.add(payment)
    await session.flush()
    return payment


def _session_metadata(stripe_session: object) -> dict[str, str]:
    raw = getattr(stripe_session, "metadata", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if hasattr(raw, "to_dict"):
        data = raw.to_dict()
        return {str(k): str(v) for k, v in data.items()}
    return {str(k): str(raw[k]) for k in raw.keys()}  # type: ignore[union-attr]


def _stripe_session_paid(stripe_session: object) -> bool:
    status = getattr(stripe_session, "payment_status", None)
    return status == "paid"


async def sync_stripe_payment_for_run(
    session: AsyncSession,
    *,
    user_id: UUID,
    run_id: UUID,
) -> bool:
    """Check Stripe for a paid checkout session and unlock the run when found."""
    if not is_stripe_configured():
        return False

    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user_id:
        return False
    if not run.output_locked:
        return True

    confirmed = await session.execute(
        select(Payment)
        .where(
            Payment.run_id == run_id,
            Payment.user_id == user_id,
            Payment.provider == "stripe",
            Payment.status == "confirmed",
        )
        .limit(1)
    )
    payment = confirmed.scalar_one_or_none()
    if payment is not None:
        await AccessService(session).unlock_run(payment.id, run_id)
        await session.commit()
        return True

    pending = await session.execute(
        select(Payment)
        .where(
            Payment.run_id == run_id,
            Payment.user_id == user_id,
            Payment.provider == "stripe",
            Payment.status == "pending",
        )
        .order_by(Payment.created_at.desc())
    )
    for payment in pending.scalars().all():
        session_id = payment.provider_payment_id
        if not session_id.startswith("cs_"):
            continue
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if not _stripe_session_paid(stripe_session):
            continue
        await confirm_stripe_payment(
            session,
            payment=payment,
            run_id=run_id,
            provider_payment_id=session_id,
        )
        return True

    listed = stripe.checkout.Session.list(limit=100)
    for stripe_session in listed.auto_paging_iter():
        metadata = _session_metadata(stripe_session)
        if metadata.get("run_id") != str(run_id):
            continue
        if metadata.get("user_id") != str(user_id):
            continue
        if not _stripe_session_paid(stripe_session):
            continue
        payment = await _payment_for_session(
            session,
            user_id=user_id,
            run_id=run_id,
            session_id=str(stripe_session.id),
        )
        await confirm_stripe_payment(
            session,
            payment=payment,
            run_id=run_id,
            provider_payment_id=str(stripe_session.id),
        )
        return True

    return False
