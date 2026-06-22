from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import stripe

from apps.web.config import settings

stripe.api_key = settings.stripe_secret_key


class StripeNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class StripeCheckoutResult:
    url: str
    session_id: str


def is_stripe_configured() -> bool:
    key = (settings.stripe_secret_key or "").strip()
    return bool(key) and not key.startswith("sk_test_fake")


def _line_item() -> dict:
    amount_cents = int(Decimal(str(settings.run_unlock_price_usd)) * 100)
    return {
        "price_data": {
            "currency": "usd",
            "product_data": {"name": "Resume Tailoring Unlock"},
            "unit_amount": amount_cents,
        },
        "quantity": 1,
    }


def create_checkout_session(
    *, user_id: str, run_id: str, email: str, resume_id: str
) -> StripeCheckoutResult:
    if not is_stripe_configured():
        raise StripeNotConfiguredError(
            "Stripe is not configured. Set STRIPE_SECRET_KEY in .env to enable checkout."
        )
    base = settings.cors_origin_list[0]
    success_url = (
        f"{base}/app/?paid=1&run_id={run_id}&resume_id={resume_id}"
    )
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=email,
        line_items=[_line_item()],
        metadata={"user_id": user_id, "run_id": run_id, "resume_id": resume_id},
        success_url=success_url,
        cancel_url=f"{base}/app/?cancelled=1&run_id={run_id}&resume_id={resume_id}",
    )
    if not session.url:
        raise RuntimeError("Stripe checkout session did not return a URL")
    return StripeCheckoutResult(url=session.url, session_id=str(session.id))


def construct_event(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
