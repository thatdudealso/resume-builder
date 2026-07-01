from __future__ import annotations

import io
import json
from decimal import Decimal

import pytest

from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume


async def _auth(client, email: str):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )


@pytest.mark.asyncio
async def test_auth_errors(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    dup = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@test.com", "password": "password123"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    assert dup.status_code == 400
    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "dup@test.com", "password": "wrongpass"},
        headers={"X-Device-Fingerprint": "fp"},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_second_resume_upload_blocked(client, monkeypatch):
    await _auth(client, "one-resume@test.com")
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nBuilt systems.",
    )
    monkeypatch.setattr("apps.web.api.v1.resumes.upload_bytes", lambda k, d, c: k)
    first = await client.post(
        "/api/v1/resumes",
        files={"file": ("r.txt", io.BytesIO(b"1"), "text/plain")},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/v1/resumes",
        files={"file": ("r2.txt", io.BytesIO(b"2"), "text/plain")},
    )
    assert second.status_code == 402


@pytest.mark.asyncio
async def test_run_stream_progress(client, monkeypatch):
    await _auth(client, "stream@test.com")
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
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python developer " * 5},
    )
    run_id = run_resp.json()["run_id"]
    from apps.web.services.run_executor import get_run_queue

    queue = get_run_queue(run_id)
    await queue.put({"event": "node_complete", "node": "prepare_inputs"})
    await queue.put({"event": "done", "locked": False})
    stream = await client.get(f"/api/v1/runs/{run_id}/stream")
    assert stream.status_code == 200
    assert "progress" in stream.text or "done" in stream.text


@pytest.mark.asyncio
async def test_score_preview_route(client, monkeypatch):
    await _auth(client, "score@test.com")
    monkeypatch.setattr(
        "apps.web.api.v1.resumes.extract_text_from_upload",
        lambda f, d: "SUMMARY\nEngineer\nEXPERIENCE\nBuilt Python APIs.",
    )
    monkeypatch.setattr("apps.web.api.v1.resumes.upload_bytes", lambda k, d, c: k)
    upload = await client.post(
        "/api/v1/resumes",
        files={"file": ("r.txt", io.BytesIO(b"data"), "text/plain")},
    )
    resume_id = upload.json()["resume_id"]

    resp = await client.post(
        "/api/v1/score/preview",
        json={"resume_id": resume_id, "jd_text": "Python API developer " * 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"] >= 0
    assert "components" in body["score"]


@pytest.mark.asyncio
async def test_export_download_redirect(client, monkeypatch):
    await _auth(client, "dl@test.com")
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
                run.is_free_trial_run = True
                run.final_output = {"plain_text": "content"}
                await s.commit()

    monkeypatch.setattr("apps.web.services.run_launcher.execute_run_background", bg)
    run_resp = await client.post(
        "/api/v1/runs",
        json={"resume_id": resume_id, "jd_text": "Python " * 10},
    )
    run_id = run_resp.json()["run_id"]
    import asyncio

    await asyncio.sleep(0.05)
    monkeypatch.setattr("apps.web.api.v1.exports.upload_bytes", lambda k, d, c: k)
    monkeypatch.setattr("apps.web.api.v1.exports.download_bytes", lambda k: b"resume content")
    export = await client.post("/api/v1/exports", json={"run_id": run_id, "format": "txt"})
    export_id = export.json()["export_id"]
    resp = await client.get(f"/api/v1/exports/{export_id}/download")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment")
    assert b"resume content" in resp.content


@pytest.mark.asyncio
async def test_stripe_webhook_unlocks_run_full(client, session, monkeypatch):
    user = await register_user(session, "stripe2@test.com", "password123")
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
        provider_payment_id="pending_y",
        idempotency_key="k-stripe-2",
        amount_usd=Decimal("9.99"),
        status="pending",
    )
    session.add_all([run, payment])
    await session.commit()
    event = {
        "id": "evt_unlock_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_live",
                "metadata": {"user_id": str(user.id), "run_id": str(run.id)},
            }
        },
    }
    monkeypatch.setattr(
        "apps.web.api.v1.webhooks.stripe.construct_event",
        lambda p, s: event,
    )
    resp = await client.post(
        "/api/v1/webhooks/stripe",
        content=json.dumps(event),
        headers={"stripe-signature": "sig"},
    )
    assert resp.status_code == 200
    import packages.db.session as db_session

    async with db_session.SessionLocal() as s:
        refreshed = await s.get(AgentRun, run.id)
        assert refreshed is not None
        assert refreshed.output_locked is False
