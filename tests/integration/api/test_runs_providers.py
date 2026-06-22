from __future__ import annotations

import io

import pytest


@pytest.mark.asyncio
async def test_list_providers_endpoint(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "providers@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    resp = await client.get("/api/v1/runs/providers")
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert any(item["id"] == "huggingface" for item in providers)


@pytest.mark.asyncio
async def test_create_run_rejects_invalid_provider(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "bad-provider@test.com", "password": "password123"},
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
    resp = await client.post(
        "/api/v1/runs",
        json={
            "resume_id": upload.json()["resume_id"],
            "jd_text": "Python developer " * 5,
            "llm_provider": "not-a-real-provider",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_run_rejects_unconfigured_openai(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "openai-off@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nBuilt systems.",
    )
    monkeypatch.setattr("apps.web.api.v1.resumes.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("apps.web.config.settings.openai_api_key", "")
    upload = await client.post(
        "/api/v1/resumes",
        files={"file": ("r.txt", io.BytesIO(b"data"), "text/plain")},
    )
    resp = await client.post(
        "/api/v1/runs",
        json={
            "resume_id": upload.json()["resume_id"],
            "jd_text": "Python developer " * 5,
            "llm_provider": "openai",
        },
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_run_rejects_invalid_variant(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "bad-variant@test.com", "password": "password123"},
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
    resp = await client.post(
        "/api/v1/runs",
        json={
            "resume_id": upload.json()["resume_id"],
            "jd_text": "Python developer " * 5,
            "variant": "aggressive",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid variant"


@pytest.mark.asyncio
async def test_create_run_returns_selected_variant(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "variant-create@test.com", "password": "password123"},
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

    async def noop_run(run_id, variant=None):
        return None

    monkeypatch.setattr("apps.web.services.run_launcher.execute_run_background", noop_run)
    resp = await client.post(
        "/api/v1/runs",
        json={
            "resume_id": upload.json()["resume_id"],
            "jd_text": "Python developer " * 5,
            "variant": "bold",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["variant"] == "bold"


@pytest.mark.asyncio
async def test_patch_variant_when_unlocked(client, monkeypatch):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "variant-ok@test.com", "password": "password123"},
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

    async def fast_run(run_id, variant=None):
        import packages.db.session as db_session
        from packages.db.models.agent_run import AgentRun

        async with db_session.SessionLocal() as bg_session:
            run = await bg_session.get(AgentRun, run_id)
            if run:
                run.status = "completed"
                run.output_locked = False
                run.final_output = {
                    "selected_variant": "balanced",
                    "sections": {
                        "summary": "A",
                        "experience": "B",
                        "skills": "C",
                        "education": "D",
                    },
                    "variants": {
                        "conservative": {"sections": {"summary": "A"}},
                        "balanced": {"sections": {"summary": "A"}},
                        "bold": {"sections": {"summary": "Bold A"}},
                    },
                    "sections_editable": {},
                }
                await bg_session.commit()

    monkeypatch.setattr("apps.web.services.run_launcher.execute_run_background", fast_run)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python developer " * 5},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    patch = await client.patch(
        f"/api/v1/runs/{run_id}/variant",
        json={"variant": "bold"},
    )
    assert patch.status_code == 200
    assert patch.json()["selected_variant"] == "bold"
