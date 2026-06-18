from __future__ import annotations

import io

import pytest

from packages.integrations.stripe_client import create_checkout_session


def test_stripe_fake_key_returns_test_url(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "sk_test_fake")
    url = create_checkout_session(user_id="u", run_id="r", email="a@b.com")
    assert "stripe.test" in url


@pytest.mark.asyncio
async def test_resume_upload_errors(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "err@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    big = await client.post(
        "/api/v1/resumes",
        files={"file": ("big.pdf", io.BytesIO(b"x" * (6 * 1024 * 1024)), "application/pdf")},
    )
    assert big.status_code == 400
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: (_ for _ in ()).throw(ValueError("bad format")),
    )
    bad = await client.post(
        "/api/v1/resumes",
        files={"file": ("bad.doc", io.BytesIO(b"x"), "application/msword")},
    )
    assert bad.status_code == 400

    monkeypatch.setattr("apps.web.api.v1.resumes.extract_text_from_upload", lambda f, d: " ")
    empty = await client.post(
        "/api/v1/resumes",
        files={"file": ("empty.txt", io.BytesIO(b" "), "text/plain")},
    )
    assert empty.status_code == 400


@pytest.mark.asyncio
async def test_run_invalid_resume(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "runerr@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    from uuid import uuid4

    resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": str(uuid4()), "jd_text": "Python developer " * 5},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_invalid_format(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "badfmt@test.com", "password": "password123"},
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
    bad = await client.post(
        "/api/v1/exports",
        json={"run_id": run.json()["run_id"], "format": "html"},
    )
    assert bad.status_code == 400
