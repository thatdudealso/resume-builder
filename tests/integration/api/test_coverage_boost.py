from __future__ import annotations

import io
from decimal import Decimal
from uuid import uuid4

import pytest

from packages.core.access.service import AccessService
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_auth_duplicate_register_and_me(client):
    headers = {"X-Device-Fingerprint": "device-a", "User-Agent": "pytest"}
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.com", "password": "password123"},
        headers=headers,
    )
    assert first.status_code == 200
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.com", "password": "password123"},
        headers=headers,
    )
    assert dup.status_code == 400
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "dup@test.com", "password": "password123"},
        headers=headers,
    )
    assert login.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == "dup@test.com"
    assert "can_upload" in body


@pytest.mark.asyncio
async def test_auth_refresh_errors(client):
    missing = await client.post("/api/v1/auth/refresh")
    assert missing.status_code == 401
    bad = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "not-a-valid-token"},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_export_locked_and_download(client, monkeypatch):
    monkeypatch.setattr("apps.web.api.v1.exports.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("apps.web.api.v1.exports.presigned_url", lambda k: "https://s3.test/file")
    async def noop_background(run_id, variant=None):
        return None

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", noop_background)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dl@test.com", "password": "password123"},
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
        json={"resume_id": upload.json()["resume_id"], "jd_text": "Python developer " * 5},
    )
    run_id = run.json()["run_id"]

    from uuid import UUID

    import packages.db.session as db_session

    async with db_session.SessionLocal() as s:
        from packages.db.models.agent_run import AgentRun

        row = await s.get(AgentRun, UUID(run_id))
        row.status = "completed"
        row.output_locked = True
        row.final_output = {"plain_text": "Locked content"}
        await s.commit()

    locked = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "txt"})
    assert locked.status_code == 402

    async with db_session.SessionLocal() as s:
        row = await s.get(AgentRun, UUID(run_id))
        row.output_locked = False
        row.is_free_trial_run = False
        row.final_output = {"plain_text": "Downloadable resume text."}
        await s.commit()

    monkeypatch.setattr("apps.web.api.v1.exports.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("packages.integrations.s3_storage.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("packages.integrations.s3_storage.presigned_url", lambda k: "https://s3.test/file")
    monkeypatch.setattr("apps.web.api.v1.exports.export_pdf", lambda t: b"%PDF-1.4")
    monkeypatch.setattr("apps.web.api.v1.exports.presigned_url", lambda k: "https://s3.test/file")
    created = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "docx"})
    assert created.status_code == 200
    export_id = created.json()["export_id"]
    dl = await client.get(f"/api/v1/exports/{export_id}/download", follow_redirects=False)
    assert dl.status_code in (302, 307)


@pytest.mark.asyncio
async def test_run_stream_and_unlock(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "stream@test.com", "password": "password123"},
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
    resume_id = upload.json()["resume_id"]

    async def bg(run_id, variant=None):
        from apps.web.services.run_executor import get_run_queue

        queue = get_run_queue(str(run_id))
        await queue.put({"event": "progress", "node": "prepare_inputs"})
        await queue.put({"event": "done", "locked": True})
        import packages.db.session as db_session
        from packages.db.models.agent_run import AgentRun

        async with db_session.SessionLocal() as s:
            run = await s.get(AgentRun, run_id)
            if run:
                run.status = "completed"
                run.output_locked = True
                run.preview_text = "Preview content"
                await s.commit()

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", bg)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python developer " * 5},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    stream = await client.get(f"/api/v1/runs/{run_id}/stream")
    assert stream.status_code == 200
    assert "event:" in stream.text
    unlock = await client.post(f"/api/v1/runs/{run_id}/unlock")
    assert unlock.status_code == 200
    assert "stripe_checkout" in unlock.json()


@pytest.mark.asyncio
async def test_billing_crypto_invoice_and_status(client, monkeypatch):
    import uuid

    suffix = uuid.uuid4().hex[:8]
    await client.post(
        "/api/v1/auth/register",
        json={"email": f"crypto-{suffix}@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": f"crypto-invoice-{suffix}"},
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
        json={"resume_id": upload.json()["resume_id"], "jd_text": "Python developer " * 5},
    )
    run_id = run.json()["run_id"]
    async def fake_invoice(**kwargs):
        return {
            "payment_id": "np_123",
            "pay_address": "bc1qtest",
            "pay_amount": "0.0001",
        }

    monkeypatch.setattr("apps.web.api.v1.billing.create_invoice", fake_invoice)
    invoice = await client.post(
        "/api/v1/billing/crypto/invoice",
        json={"run_id": run_id, "pay_currency": "btc"},
    )
    assert invoice.status_code == 200
    payment_id = invoice.json()["payment_id"]
    poll = await client.get(f"/api/v1/billing/crypto/{payment_id}")
    assert poll.status_code == 200
    status = await client.get("/api/v1/billing/status")
    assert status.status_code == 200
    assert "pending_payments" in status.json()
    wrong = await client.get(f"/api/v1/billing/crypto/{uuid4()}")
    assert wrong.status_code == 404


@pytest.mark.asyncio
async def test_run_get_with_final_output(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "final@test.com", "password": "password123"},
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
    resume_id = upload.json()["resume_id"]

    async def bg(run_id, variant=None):
        import packages.db.session as db_session
        from packages.db.models.agent_run import AgentRun

        async with db_session.SessionLocal() as s:
            run = await s.get(AgentRun, run_id)
            if run:
                run.status = "completed"
                run.output_locked = False
                run.final_output = {"plain_text": "Visible output"}
                await s.commit()

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", bg)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python developer " * 5},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    detail = await client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json().get("final_output") is not None


@pytest.mark.asyncio
async def test_access_payment_view_and_unlock(session):
    user = await register_user(session, "payview@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
        status="completed",
        final_output={"plain_text": "secret"},
    )
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="stripe",
        provider_payment_id="pi_test",
        idempotency_key="idem-1",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.flush()
    access = AccessService(session)
    assert await access.can_view_output(user.id, run) is False
    await access.unlock_run(payment.id, run.id)
    await session.refresh(run)
    assert run.output_locked is False
    assert await access.can_view_output(user.id, run) is True
    assert await access.can_export(user.id, run) is True
    run.is_free_trial_run = True
    assert await access.can_export(user.id, run) is True
    with pytest.raises(ValueError):
        await access.get_snapshot(uuid4())
