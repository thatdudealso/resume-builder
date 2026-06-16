from __future__ import annotations

from decimal import Decimal

import stripe

from apps.web.config import settings

stripe.api_key = settings.stripe_secret_key


def create_checkout_session(*, user_id: str, run_id: str, email: str) -> str:
    if not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test_fake"):
        return f"https://checkout.stripe.test/session/{run_id}"
    amount_cents = int(Decimal(str(settings.run_unlock_price_usd)) * 100)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=email,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Resume Tailoring Unlock"},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        metadata={"user_id": user_id, "run_id": run_id},
        success_url=f"{settings.cors_origin_list[0]}/app/?paid=1&run_id={run_id}",
        cancel_url=f"{settings.cors_origin_list[0]}/app/?cancelled=1",
    )
    return session.url or ""


def construct_event(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
