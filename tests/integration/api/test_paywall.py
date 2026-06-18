from __future__ import annotations

import io

import pytest


async def _register_and_login(client, email: str):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )


@pytest.mark.asyncio
async def test_paywall_flow(client, monkeypatch):
    await _register_and_login(client, "paywall@test.com")
    pdf_bytes = b"%PDF-1.4\n" + b"x" * 100
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nPython developer 2020-2022.",
    )
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.upload_bytes",
        lambda k, d, c: k,
    )
    upload = await client.post(
        "/api/v1/resumes",
        files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert upload.status_code == 200
    resume_id = upload.json()["resume_id"]
    jd = "Python API developer with PostgreSQL. " * 3

    async def fast_run(run_id, variant=None):
        import packages.db.session as db_session
        from packages.core.access.service import AccessService

        async with db_session.SessionLocal() as bg_session:
            run = await bg_session.get(
                __import__("packages.db.models.agent_run", fromlist=["AgentRun"]).AgentRun,
                run_id,
            )
            if run:
                run.status = "completed"
                run.final_output = {"plain_text": "Tailored resume content here."}
                run.preview_text = "Tailored resume"
                if run.is_free_trial_run:
                    await AccessService(bg_session).mark_free_trial_used(run.user_id)
                await bg_session.commit()

    monkeypatch.setattr("apps.web.api.v1.runs._run_background", fast_run)

    run1 = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": jd},
    )
    assert run1.status_code == 200
    assert run1.json()["output_locked"] is False

    import asyncio

    await asyncio.sleep(0.1)

    run2 = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": jd + " extra"},
    )
    assert run2.status_code == 200
    assert run2.json()["output_locked"] is True
    run2_id = run2.json()["run_id"]

    detail = await client.get(f"/api/v1/runs/{run2_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["output_locked"] is True
    assert body.get("final_output") is None


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()
