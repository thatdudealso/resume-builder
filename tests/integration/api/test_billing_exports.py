from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_locked_export_returns_402(client, monkeypatch):
    client.headers["X-Device-Fingerprint"] = "fp-locked"
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
                run.output_locked = True
                run.final_output = {"plain_text": "secret"}
                await s.commit()

    monkeypatch.setattr("apps.web.services.run_launcher.execute_run_background", bg)
    await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python " * 10},
    )
    await client.get("/api/v1/resumes")
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Java " * 10},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    export = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "docx"})
    assert export.status_code == 402


@pytest.mark.asyncio
async def test_crypto_invoice_endpoint(client, monkeypatch):
    client.headers["X-Device-Fingerprint"] = "fp-crypto2"
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
    invoice = await client.post(
        "/api/v1/billing/crypto/invoice",
        json={"run_id": run.json()["run_id"], "pay_currency": "btc"},
    )
    assert invoice.status_code == 200
    assert invoice.json()["pay_address"]
