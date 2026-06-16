from __future__ import annotations

import io
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_login_and_refresh_flow(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "flow@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "device-1", "User-Agent": "pytest"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "flow@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "device-1"},
    )
    assert login.status_code == 200
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200


@pytest.mark.asyncio
async def test_stripe_checkout_and_poll(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "stripe3@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
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
        lambda **kwargs: "https://checkout.test/session",
    )
    checkout = await client.post(
        "/api/v1/billing/stripe/checkout",
        json={"run_id": run.json()["run_id"]},
    )
    assert checkout.status_code == 200
    payment_id = checkout.json()["payment_id"]
    poll = await client.get(f"/api/v1/billing/crypto/{payment_id}")
    assert poll.status_code == 200


@pytest.mark.asyncio
async def test_run_not_found(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "nf@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
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
