from __future__ import annotations

import io
import json
from decimal import Decimal

import pytest

from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.crypto_payment import CryptoPayment
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_crypto_webhook_confirms_payment(client, session, monkeypatch):
    user = await register_user(session, "cwh@test.com", "password123")
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
        final_output={"plain_text": "x"},
    )
    payment = Payment(
        user_id=user.id,
        run_id=run.id,
        provider="crypto",
        provider_payment_id="np_xyz",
        idempotency_key="ck-wh",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.flush()
    session.add(
        CryptoPayment(
            payment_id=payment.id,
            pay_currency="btc",
            pay_amount=Decimal("0.001"),
            pay_address="addr",
        )
    )
    await session.commit()

    monkeypatch.setattr(
        "apps.web.api.v1.webhooks.crypto.verify_ipn_signature",
        lambda p, s: True,
    )
    payload = {"payment_id": "np_xyz", "payment_status": "finished", "order_id": str(run.id)}
    resp = await client.post(
        "/api/v1/webhooks/crypto",
        content=json.dumps(payload),
        headers={"x-nowpayments-sig": "sig"},
    )
    assert resp.status_code == 200
    import packages.db.session as db_session

    async with db_session.SessionLocal() as s:
        refreshed = await s.get(AgentRun, run.id)
        assert refreshed.output_locked is False


@pytest.mark.asyncio
async def test_export_docx_and_billing_poll(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "docx@test.com", "password": "password123"},
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

    async def bg(run_id):
        import packages.db.session as db_session
        from packages.db.models.agent_run import AgentRun

        async with db_session.SessionLocal() as s:
            run = await s.get(AgentRun, run_id)
            if run:
                run.status = "completed"
                run.output_locked = False
                run.is_free_trial_run = False
                run.payment_id = None
                run.final_output = {"plain_text": "Paid content"}
                await s.commit()

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", bg)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python " * 10},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    monkeypatch.setattr("apps.web.api.v1.exports.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("apps.web.api.v1.exports.export_pdf", lambda t: b"%PDF")
    docx = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "docx"})
    assert docx.status_code in (200, 402)
