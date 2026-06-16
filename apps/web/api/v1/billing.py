from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from apps.web.dependencies import get_current_user, get_db
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.user import User
from packages.integrations.crypto.nowpayments import create_invoice
from packages.integrations.stripe_client import create_checkout_session

router = APIRouter(prefix="/billing", tags=["billing"])


class StripeCheckoutRequest(BaseModel):
    run_id: UUID


class CryptoInvoiceRequest(BaseModel):
    run_id: UUID
    pay_currency: str = "btc"


@router.get("/status")
async def billing_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    payments = await session.execute(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
    )
    rows = payments.scalars().all()
    unlocked = await session.execute(
        select(AgentRun).where(AgentRun.user_id == user.id, AgentRun.output_locked.is_(False))
    )
    return {
        "free_trial_used": user.free_trial_used,
        "pending_payments": [
            {
                "payment_id": str(p.id),
                "status": p.status,
                "run_id": str(p.run_id) if p.run_id else None,
            }
            for p in rows
            if p.status == "pending"
        ],
        "unlocked_runs": [str(r.id) for r in unlocked.scalars().all()],
        "price_usd": settings.run_unlock_price_usd,
    }


@router.post("/stripe/checkout")
async def stripe_checkout(
    body: StripeCheckoutRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, body.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id=f"pending_{uuid.uuid4().hex}",
        idempotency_key=f"stripe-{run.id}-{uuid.uuid4().hex[:8]}",
        amount_usd=Decimal(str(settings.run_unlock_price_usd)),
        status="pending",
    )
    session.add(payment)
    await session.commit()
    url = create_checkout_session(user_id=str(user.id), run_id=str(run.id), email=user.email)
    return {"checkout_url": url, "payment_id": str(payment.id)}


@router.post("/crypto/invoice")
async def crypto_invoice(
    body: CryptoInvoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, body.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    invoice = await create_invoice(
        user_id=str(user.id), run_id=str(run.id), pay_currency=body.pay_currency
    )
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="crypto",
        provider_payment_id=str(invoice.get("payment_id", uuid.uuid4().hex)),
        idempotency_key=f"crypto-{run.id}-{uuid.uuid4().hex[:8]}",
        amount_usd=Decimal(str(settings.run_unlock_price_usd)),
        status="pending",
    )
    session.add(payment)
    await session.flush()
    from packages.db.models.crypto_payment import CryptoPayment

    session.add(
        CryptoPayment(
            payment_id=payment.id,
            pay_currency=body.pay_currency,
            pay_amount=Decimal(str(invoice.get("pay_amount", "0"))),
            pay_address=invoice.get("pay_address"),
        )
    )
    await session.commit()
    return {
        "payment_id": str(payment.id),
        "pay_address": invoice.get("pay_address"),
        "pay_amount": invoice.get("pay_amount"),
        "pay_currency": body.pay_currency,
    }


@router.get("/crypto/{payment_id}")
async def crypto_status(
    payment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {"payment_id": str(payment.id), "status": payment.status, "run_id": str(payment.run_id)}
