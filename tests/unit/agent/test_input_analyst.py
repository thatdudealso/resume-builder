from __future__ import annotations

import pytest

from packages.agent.analysts.input_analyst import analyze_inputs_combined, analyze_inputs_sequential
from packages.agent.providers._mock import mock_complete
from packages.agent.providers.openai_provider import OpenAIProvider

_JD = "Python developer with PostgreSQL required."
_RESUME = "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python\nSKILLS\nPython"


@pytest.mark.asyncio
async def test_analyze_inputs_combined_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.openai_api_key", "")
    provider = OpenAIProvider()
    jd, resume = await analyze_inputs_combined(_JD, _RESUME, provider)
    assert jd.must_have
    assert resume.sections_present["experience"] is True


@pytest.mark.asyncio
async def test_analyze_inputs_combined_configured_success(monkeypatch):
    monkeypatch.setattr(OpenAIProvider, "is_configured", lambda self: True)

    async def fake_complete(self, task, prompt, *, json_mode=False):
        return mock_complete(task, prompt, json_mode=json_mode)

    monkeypatch.setattr(OpenAIProvider, "complete", fake_complete)
    provider = OpenAIProvider()
    jd, resume = await analyze_inputs_combined(_JD, _RESUME, provider)
    assert jd.must_have
    assert resume.sections_present["experience"] is True


@pytest.mark.asyncio
async def test_analyze_inputs_combined_falls_back_on_provider_error(monkeypatch):
    monkeypatch.setattr(OpenAIProvider, "is_configured", lambda self: True)

    async def fail_complete(self, task, prompt, *, json_mode=False):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(OpenAIProvider, "complete", fail_complete)
    provider = OpenAIProvider()
    jd, resume = await analyze_inputs_combined(_JD, _RESUME, provider)
    assert jd.must_have
    assert resume.sections_present["experience"] is True


@pytest.mark.asyncio
async def test_analyze_inputs_sequential():
    provider = OpenAIProvider()
    jd, resume = await analyze_inputs_sequential(_JD, _RESUME, provider)
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
