from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_db
from packages.core.access.service import AccessService
from packages.db.models.agent_run import AgentRun
from packages.db.models.crypto_webhook_event import CryptoWebhookEvent
from packages.db.models.payment import Payment
from packages.integrations.crypto.nowpayments import verify_ipn_signature

router = APIRouter(prefix="/webhooks/crypto", tags=["webhooks"])


@router.post("")
async def crypto_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("x-nowpayments-sig", "")
    if not verify_ipn_signature(payload, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = json.loads(payload)
    event_id = str(data.get("payment_id", data.get("invoice_id", "")))
    existing = await session.execute(
        select(CryptoWebhookEvent).where(CryptoWebhookEvent.provider_event_id == event_id)
    )
    if existing.scalar_one_or_none():
        return {"received": True}

    payment_row = await session.execute(
        select(Payment).where(Payment.provider_payment_id == event_id)
    )
    payment = payment_row.scalar_one_or_none()
    session.add(
        CryptoWebhookEvent(
            provider_event_id=event_id,
            payment_id=payment.id if payment else None,
            event_type=str(data.get("payment_status", "unknown")),
            payload=data,
        )
    )

    if payment and data.get("payment_status") in ("finished", "confirmed"):
        payment.status = "confirmed"
        payment.confirmed_at = datetime.now(UTC)
        if payment.run_id:
            await AccessService(session).unlock_run(payment.id, payment.run_id)
        elif data.get("order_id"):
            run = await session.get(AgentRun, UUID(str(data["order_id"])))
            if run:
                payment.run_id = run.id
                await AccessService(session).unlock_run(payment.id, run.id)

    await session.commit()
    return {"received": True}
