from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from packages.agent.sections.orchestrator import build_all_variants


@pytest.mark.asyncio
async def test_build_all_variants_only_builds_selected_style():
    agent_service = AsyncMock()
    agent_service.complete = AsyncMock(return_value="Rewritten section")

    state = {
        "master_resume_structured": {
            "summary": "Engineer",
            "experience": "",
            "skills": "",
            "education": "",
        },
        "section_drafts": {"summary": "Engineer"},
        "sections_to_tailor": ["summary"],
        "user_added_sections": {},
        "keyword_gaps": [],
        "jd_text": "Python role",
        "selected_variant": "bold",
    }

    with patch(
        "packages.agent.sections.orchestrator.rewrite_section",
        new_callable=AsyncMock,
        return_value="Tailored",
    ) as rewrite:
        variants = await build_all_variants(state, agent_service)

    assert set(variants) == {"bold"}
    assert rewrite.await_count == 1


@pytest.mark.asyncio
async def test_build_all_variants_invalid_selected_falls_back_to_balanced():
    agent_service = AsyncMock()
    state = {
        "master_resume_structured": {
            "summary": "Engineer",
            "experience": "",
            "skills": "",
            "education": "",
        },
        "section_drafts": {"summary": "Engineer"},
        "sections_to_tailor": ["summary"],
        "user_added_sections": {},
        "keyword_gaps": [],
        "jd_text": "Python role",
        "selected_variant": "not-a-real-variant",
    }
    with patch(
        "packages.agent.sections.orchestrator.rewrite_section",
        new_callable=AsyncMock,
        return_value="Tailored",
    ):
        variants = await build_all_variants(state, agent_service)
    assert set(variants) == {"balanced"}


@pytest.mark.asyncio
async def test_build_all_variants_empty_sections_returns_empty_variant():
    agent_service = AsyncMock()
    state = {
        "master_resume_structured": {
            "summary": "",
            "experience": "",
            "skills": "",
            "education": "",
        },
        "section_drafts": {},
        "sections_to_tailor": [],
        "user_added_sections": {},
        "keyword_gaps": [],
        "jd_text": "Python role",
        "selected_variant": "conservative",
    }
    variants = await build_all_variants(state, agent_service)
    assert variants == {"conservative": {}}
    agent_service.complete.assert_not_called()
