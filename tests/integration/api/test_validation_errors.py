from __future__ import annotations

import io

import pytest

from packages.integrations.stripe_client import (
    StripeNotConfiguredError,
    create_checkout_session,
    is_stripe_configured,
)


def test_stripe_not_configured_when_key_missing(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "")
    assert is_stripe_configured() is False
    with pytest.raises(StripeNotConfiguredError):
        create_checkout_session(user_id="u", run_id="r", email="a@b.com", resume_id="res1")


def test_stripe_not_configured_for_fake_test_key(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.stripe_secret_key", "sk_test_fake")
    assert is_stripe_configured() is False


@pytest.mark.asyncio
async def test_resume_upload_errors(client, monkeypatch):
    client.headers["X-Device-Fingerprint"] = "fp-err"
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
    client.headers["X-Device-Fingerprint"] = "fp-runerr"
    from uuid import uuid4

    resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": str(uuid4()), "jd_text": "Python developer " * 5},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_invalid_format(client, monkeypatch):
    client.headers["X-Device-Fingerprint"] = "fp-badfmt"
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
