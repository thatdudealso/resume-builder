from __future__ import annotations

import pytest

from apps.web.services.run_editor import (
    add_section_and_retailor,
    select_variant,
    update_section_override,
)
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


def _sample_final_output() -> dict:
    sections = {
        "summary": "Original summary",
        "experience": "Original experience",
        "skills": "Python",
        "education": "BS CS",
    }
    return {
        "selected_variant": "balanced",
        "sections": sections,
        "plain_text": "SUMMARY\nOriginal summary",
        "variants": {
            "conservative": {"sections": sections, "plain_text": "conservative"},
            "balanced": {"sections": sections, "plain_text": "balanced"},
            "bold": {"sections": {**sections, "summary": "Bold summary"}, "plain_text": "bold"},
        },
        "sections_editable": {
            "summary": {
                "original": "Original summary",
                "proposed_by_variant": {"balanced": "Original summary"},
                "user_override": None,
            }
        },
        "sections_missing": [],
    }


@pytest.mark.asyncio
async def test_select_variant_updates_output(session):
    user = await register_user(session, "variant@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
        final_output=_sample_final_output(),
    )
    session.add(run)
    await session.commit()

    final = await select_variant(session, run, "bold")
    assert final["selected_variant"] == "bold"
    assert final["sections"]["summary"] == "Bold summary"


@pytest.mark.asyncio
async def test_select_variant_rejects_unknown_name(session):
    user = await register_user(session, "bad-variant@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
        final_output=_sample_final_output(),
    )
    session.add(run)
    await session.commit()

    with pytest.raises(ValueError, match="Invalid variant"):
        await select_variant(session, run, "not-a-variant")


@pytest.mark.asyncio
async def test_update_section_override(session):
    user = await register_user(session, "edit@test.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.pdf",
        s3_key="k",
        raw_text="SUMMARY\nOld summary\nEXPERIENCE\nBuilt APIs\nSKILLS\nPython\n",
    )
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
        final_output=_sample_final_output(),
    )
    session.add(run)
    await session.commit()

    final = await update_section_override(
        session, run, resume, section="summary", content="Edited summary"
    )
    assert final["sections"]["summary"] == "Edited summary"
    assert final["sections_editable"]["summary"]["user_override"] == "Edited summary"


@pytest.mark.asyncio
async def test_add_section_and_retailor(session, monkeypatch):
    user = await register_user(session, "add-section@test.com", "password123")
    await session.flush()
    resume = MasterResume(
        user_id=user.id,
        filename="r.pdf",
        s3_key="k",
        raw_text="SUMMARY\nOld summary\nEXPERIENCE\nBuilt APIs\nSKILLS\nPython\n",
    )
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=False,
        llm_provider="huggingface",
        final_output={**_sample_final_output(), "sections_missing": ["education"]},
    )
    session.add(run)
    await session.commit()

    async def fake_retailor(state, agent_service, section, content):
        return {
            "conservative": content,
            "balanced": content,
            "bold": content,
        }

    monkeypatch.setattr(
        "apps.web.services.run_editor.retailor_section",
        fake_retailor,
    )
    final = await add_section_and_retailor(
        session, run, resume, section="education", content="BS Computer Science"
    )
    assert "education" not in final.get("sections_missing", [])
    assert final["variants"]["balanced"]["sections"]["education"] == "BS Computer Science"
