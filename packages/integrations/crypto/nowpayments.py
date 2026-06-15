from __future__ import annotations

import hashlib
import hmac
import uuid
from decimal import Decimal

import httpx

from apps.web.config import settings


def verify_ipn_signature(payload: bytes, signature: str) -> bool:
    if not settings.nowpayments_ipn_secret:
        return settings.env in ("local", "test")
    digest = hmac.new(settings.nowpayments_ipn_secret.encode(), payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


async def create_invoice(*, user_id: str, run_id: str, pay_currency: str = "btc") -> dict:
    if not settings.nowpayments_api_key or settings.nowpayments_api_key == "test":
        return {
            "payment_id": f"np_{uuid.uuid4().hex[:12]}",
            "pay_address": "bc1qmockaddress000000000000000000",
            "pay_amount": "0.00015",
            "pay_currency": pay_currency,
        }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.nowpayments.io/v1/invoice",
            headers={"x-api-key": settings.nowpayments_api_key},
            json={
                "price_amount": settings.run_unlock_price_usd,
                "price_currency": "usd",
                "pay_currency": pay_currency,
                "order_id": run_id,
                "order_description": f"Unlock run {run_id}",
            },
        )
        resp.raise_for_status()
        return resp.json()
