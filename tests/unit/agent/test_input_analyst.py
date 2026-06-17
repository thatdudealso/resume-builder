from __future__ import annotations

import pytest

from packages.agent.analysts.input_analyst import analyze_inputs_combined
from packages.agent.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_analyze_inputs_combined_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.openai_api_key", "")
    provider = OpenAIProvider()
    jd, resume = await analyze_inputs_combined(
        "Python developer with PostgreSQL required.",
        "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python\nSKILLS\nPython",
        provider,
    )
    assert jd.must_have
    assert resume.sections_present["experience"] is True


@pytest.mark.asyncio
async def test_agent_service_uses_combined_analysis():
    from packages.agent.service import AgentService

    service = AgentService("openai")
    analysis = await service.analyze_inputs(
        "Python developer with PostgreSQL required.",
        "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python\nSKILLS\nPython",
    )
    assert analysis["match_score_before"]["overall"] >= 0
    assert "jd_analysis" in analysis
    assert "resume_analysis" in analysis
