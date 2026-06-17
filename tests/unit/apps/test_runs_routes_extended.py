from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.web.api.v1.runs import SelectVariantRequest, list_llm_providers, patch_run_variant
from packages.core.security.jwt import register_user
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


@pytest.mark.asyncio
async def test_list_llm_providers():
    result = await list_llm_providers()
    ids = {item["id"] for item in result["providers"]}
    assert "huggingface" in ids
    assert "openai" in ids


@pytest.mark.asyncio
async def test_patch_variant_requires_unlock(session):
    user = await register_user(session, "locked-variant@test.com", "password123")
    await session.flush()
    resume = MasterResume(user_id=user.id, filename="r.pdf", s3_key="k", raw_text="x " * 30)
    session.add(resume)
    await session.flush()
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text="jd " * 10,
        output_locked=True,
        final_output={"variants": {}},
    )
    session.add(run)
    await session.commit()

    with pytest.raises(HTTPException) as exc:
        await patch_run_variant(
            run.id,
            SelectVariantRequest(variant="balanced"),
            user=user,
            session=session,
        )
    assert exc.value.status_code == 403
