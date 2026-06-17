from __future__ import annotations

import pytest

from packages.agent.changelog.builder import build_changelog
from packages.agent.graph import run_agent
from packages.agent.schemas.variants import SECTION_KEYS
from packages.agent.service import AgentService

_INITIAL = {
    "run_id": "r1",
    "user_id": "u1",
    "llm_provider": "huggingface",
    "master_resume_text": (
        "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python for 2020-2022.\nSKILLS\nPython, SQL"
    ),
    "jd_text": "Seeking Python API developer with PostgreSQL skills required.",
    "retry_count": 0,
}


@pytest.mark.asyncio
async def test_agent_graph_e2e():
    service = AgentService("huggingface")
    result = await run_agent(_INITIAL, service)
    assert result.get("final_output")
    assert result.get("validation_passed") is True
    assert result.get("match_score_before")
    assert result.get("match_score_after")
    final = result["final_output"]
    assert "variants" in final
    assert "balanced" in final["variants"]
    assert len(final["variants"]) == 1
    assert final.get("changelog") is not None
    match = final["match_score"]
    assert match["previous_overall"] is not None
    assert match["current_overall"] is not None


@pytest.mark.asyncio
async def test_agent_graph_respects_provider_selection(monkeypatch):
    monkeypatch.setattr(
        "packages.agent.providers.openai_provider.OpenAIProvider.is_configured",
        lambda self: False,
    )
    initial = {**_INITIAL, "llm_provider": "openai"}
    service = AgentService("openai")
    result = await run_agent(initial, service)
    assert result.get("final_output")
    assert result["final_output"]["llm_provider"] == "openai"


def test_changelog_detects_changes():
    original = {key: f"Original {key}" for key in SECTION_KEYS}
    variants = {
        "balanced": {key: f"Updated {key}" for key in SECTION_KEYS},
        "conservative": original,
        "bold": {key: f"Bold {key}" for key in SECTION_KEYS},
    }
    changelog = build_changelog(original, variants)
    assert any(entry["variant"] == "balanced" for entry in changelog)
