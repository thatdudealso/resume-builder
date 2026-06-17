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
