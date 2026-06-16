from __future__ import annotations

import io

import pytest


async def _register(client, email: str):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )


@pytest.mark.asyncio
async def test_resume_upload_and_list(client, monkeypatch):
    await _register(client, "resume@test.com")
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nBuilt systems.",
    )
    monkeypatch.setattr("apps.web.api.v1.resumes.upload_bytes", lambda k, d, c: k)
    resp = await client.post(
        "/api/v1/resumes",
        files={"file": ("r.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 200
    listed = await client.get("/api/v1/resumes")
    assert len(listed.json()["resumes"]) == 1


@pytest.mark.asyncio
async def test_export_locked_then_unlocked(client, session, monkeypatch):
    await _register(client, "export@test.com")
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

    async def fake_run(run_id):
        import packages.db.session as db_session
        from packages.db.models.agent_run import AgentRun

        async with db_session.SessionLocal() as bg:
            run = await bg.get(AgentRun, run_id)
            if run:
                run.status = "completed"
                run.final_output = {"plain_text": "Exported content"}
                run.preview_text = "Exported"
                run.output_locked = False
                run.is_free_trial_run = True
                await bg.commit()

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", fake_run)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python developer " * 5},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    monkeypatch.setattr("apps.web.api.v1.exports.upload_bytes", lambda k, d, c: k)
    export = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "txt"})
    assert export.status_code == 200


@pytest.mark.asyncio
async def test_billing_and_unlock_endpoints(client, monkeypatch):
    await _register(client, "bill2@test.com")
    status = await client.get("/api/v1/billing/status")
    assert status.status_code == 200
    unlock = await client.post(f"/api/v1/runs/{__import__('uuid').uuid4()}/unlock")
    assert unlock.status_code == 404


@pytest.mark.asyncio
async def test_deployments_latest(client):
    r = await client.get("/deployments/latest")
    assert r.status_code == 200
