from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from apps.web.dependencies import get_db
from packages.core.access.service import AccessService
from packages.db.models.payment import Payment
from packages.db.models.stripe_event import StripeEvent
from packages.integrations.stripe_client import construct_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks"])


def _event_payload(event: object) -> dict:
    if hasattr(event, "to_dict"):
        return event.to_dict()  # type: ignore[no-any-return]
    if isinstance(event, dict):
        return event
    return {"raw": str(event)}


@router.post("")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        raw_event = construct_event(payload, sig)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    event = _event_payload(raw_event)
    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))

    existing = await session.execute(
        select(StripeEvent).where(StripeEvent.stripe_event_id == event_id)
    )
    if existing.scalar_one_or_none():
        return {"received": True}

    session.add(
        StripeEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            payload=event,
        )
    )

    if event_type == "checkout.session.completed":
        session_object = event.get("data", {}).get("object", {})
        metadata = session_object.get("metadata") or {}
        run_id = metadata.get("run_id")
        user_id = metadata.get("user_id")
        if run_id and user_id:
            result = await session.execute(
                select(Payment)
                .where(
                    Payment.run_id == UUID(run_id),
                    Payment.user_id == UUID(user_id),
                    Payment.provider == "stripe",
                )
                .order_by(Payment.created_at.desc())
                .limit(1)
            )
            payment = result.scalar_one_or_none()
            if payment is None:
                payment = Payment(
                    user_id=UUID(user_id),
                    run_id=UUID(run_id),
                    provider="stripe",
                    provider_payment_id=str(session_object.get("id", "")),
                    idempotency_key=f"stripe-wh-{event_id}",
                    amount_usd=settings.run_unlock_price_usd,
                    status="pending",
                )
                session.add(payment)
                await session.flush()
            payment.status = "confirmed"
            payment.confirmed_at = datetime.now(UTC)
            payment.provider_payment_id = str(session_object.get("id", ""))
            await AccessService(session).unlock_run(payment.id, UUID(run_id))
            logger.info("Stripe webhook unlocked run_id=%s user_id=%s", run_id, user_id)
        else:
            logger.warning(
                "Stripe checkout.session.completed missing metadata run_id=%s user_id=%s",
                run_id,
                user_id,
            )

    await session.commit()
    return {"received": True}
