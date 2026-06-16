from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_db
from packages.core.access.service import AccessService
from packages.db.models.payment import Payment
from packages.db.models.stripe_event import StripeEvent
from packages.integrations.stripe_client import construct_event

router = APIRouter(prefix="/webhooks/stripe", tags=["webhooks"])


@router.post("")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = construct_event(payload, sig)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    existing = await session.execute(
        select(StripeEvent).where(StripeEvent.stripe_event_id == event["id"])
    )
    if existing.scalar_one_or_none():
        return {"received": True}

    session.add(
        StripeEvent(
            stripe_event_id=event["id"],
            event_type=event["type"],
            payload=dict(event),
        )
    )

    if event["type"] == "checkout.session.completed":
        metadata = event["data"]["object"].get("metadata", {})
        run_id = metadata.get("run_id")
        user_id = metadata.get("user_id")
        if run_id and user_id:
            result = await session.execute(
                select(Payment).where(
                    Payment.run_id == UUID(run_id),
                    Payment.user_id == UUID(user_id),
                    Payment.provider == "stripe",
                )
            )
            payment = result.scalar_one_or_none()
            if payment is None:
                payment = Payment(
                    user_id=UUID(user_id),
                    run_id=UUID(run_id),
                    provider="stripe",
                    provider_payment_id=event["data"]["object"]["id"],
                    idempotency_key=f"stripe-wh-{event['id']}",
                    amount_usd=9.99,
                    status="pending",
                )
                session.add(payment)
                await session.flush()
            payment.status = "confirmed"
            payment.confirmed_at = datetime.now(UTC)
            payment.provider_payment_id = event["data"]["object"]["id"]
            await AccessService(session).unlock_run(payment.id, UUID(run_id))

    await session.commit()
    return {"received": True}
