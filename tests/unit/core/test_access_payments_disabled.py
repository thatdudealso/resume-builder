from __future__ import annotations

from unittest.mock import patch

import pytest

from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_can_start_run_free_when_payments_disabled(session):
    user = await register_user(session, "payments-disabled-run@example.com", "password123")
    user.free_trial_used = True
    await session.flush()

    access = AccessService(session)
    with patch("packages.core.access.service.settings") as mock_settings:
        mock_settings.payments_enabled = False
        decision = await access.can_start_run(user.id)

    assert decision.mode == RunAccessMode.FREE


@pytest.mark.asyncio
async def test_can_upload_true_when_payments_disabled(session):
    user = await register_user(session, "payments-disabled-upload@example.com", "password123")
    user.free_trial_used = True
    await session.flush()

    access = AccessService(session)
    with patch("packages.core.access.service.settings") as mock_settings:
        mock_settings.payments_enabled = False
        assert await access.can_upload_resume(user.id) is True


@pytest.mark.asyncio
async def test_snapshot_can_upload_true_when_payments_disabled(session):
    user = await register_user(session, "payments-disabled-snapshot@example.com", "password123")
    user.free_trial_used = True
    await session.flush()

    access = AccessService(session)
    with patch("packages.core.access.service.settings") as mock_settings:
        mock_settings.payments_enabled = False
        assert (await access.get_snapshot(user.id)).can_upload is True


@pytest.mark.asyncio
async def test_can_view_output_true_when_payments_disabled(session):
    user = await register_user(session, "payments-disabled-view@example.com", "password123")
    user.free_trial_used = True
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.pdf",
        s3_key="k",
        raw_text="text " * 20,
    )
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="job " * 10,
        output_locked=True,
    )
    session.add(run)
    await session.flush()

    access = AccessService(session)
    with patch("packages.core.access.service.settings") as mock_settings:
        mock_settings.payments_enabled = False
        assert await access.can_view_output(user.id, run) is True


@pytest.mark.asyncio
async def test_can_export_true_when_payments_disabled(session):
    user = await register_user(session, "payments-disabled-export@example.com", "password123")
    user.free_trial_used = True
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.pdf",
        s3_key="k",
        raw_text="text " * 20,
    )
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="job " * 10,
        output_locked=True,
        is_free_trial_run=False,
    )
    session.add(run)
    await session.flush()

    access = AccessService(session)
    with patch("packages.core.access.service.settings") as mock_settings:
        mock_settings.payments_enabled = False
        assert await access.can_export(user.id, run) is True
