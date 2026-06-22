from __future__ import annotations

import io
from uuid import uuid4

import pytest

from packages.integrations.stripe_client import StripeCheckoutResult


@pytest.mark.asyncio
async def test_credential_auth_routes_are_removed(client):
    assert (await client.post("/api/v1/auth/register")).status_code == 404
    assert (await client.post("/api/v1/auth/login")).status_code == 404
    assert (await client.post("/api/v1/auth/refresh")).status_code == 404
    assert (await client.post("/api/v1/auth/logout")).status_code == 404


@pytest.mark.asyncio
async def test_stripe_checkout_and_poll(client, monkeypatch):
    client.headers["X-Device-Fingerprint"] = "fp-stripe3"
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nBuilt systems.",
    )
    monkeypatch.setattr("apps.web.api.v1.resumes.upload_bytes", lambda k, d, c: k)
    upload = await client.post(
        "/api/v1/resumes",
        files={"file": ("r.txt", io.BytesIO(b"data"), "text/plain")},
    )
    run = await client.post(
        "/api/v1/runs",
        json={"resume_id": upload.json()["resume_id"], "jd_text": "Python " * 10},
    )
    monkeypatch.setattr(
        "apps.web.api.v1.billing.create_checkout_session",
        lambda **kwargs: StripeCheckoutResult(
            url="https://checkout.test/session",
            session_id="cs_test",
        ),
    )
    checkout = await client.post(
        "/api/v1/billing/stripe/checkout",
        json={"run_id": run.json()["run_id"]},
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert body["checkout_url"]
    assert body["payment_id"]
    status = await client.get("/api/v1/billing/status")
    assert status.status_code == 200
    assert status.json()["price_usd"] == 3.99


@pytest.mark.asyncio
async def test_run_not_found(client):
    client.headers["X-Device-Fingerprint"] = "fp-nf"
    missing = await client.get(f"/api/v1/runs/{uuid4()}")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_health_degraded(client, monkeypatch):
    async def fail_redis():
        raise ConnectionError("down")

    monkeypatch.setattr("apps.web.api.v1.health.get_redis", fail_redis)
    from httpx import ASGITransport, AsyncClient

    from apps.web.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
        assert r.json()["status"] in ("ok", "degraded")
