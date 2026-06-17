from __future__ import annotations

import pytest

from packages.agent.providers.anthropic_provider import AnthropicProvider
from packages.agent.providers.base import AgentTask
from packages.agent.providers.gemini_provider import GeminiProvider
from packages.agent.providers.grok_provider import GrokProvider
from packages.agent.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.openai_api_key", "")
    provider = OpenAIProvider()
    out = await provider.complete(AgentTask.JD_ANALYSIS, "Analyze this JD")
    assert out


@pytest.mark.asyncio
async def test_anthropic_provider_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.anthropic_api_key", "")
    provider = AnthropicProvider()
    out = await provider.complete(AgentTask.RESUME_ANALYSIS, "Analyze resume")
    assert out


@pytest.mark.asyncio
async def test_gemini_provider_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.gemini_api_key", "")
    provider = GeminiProvider()
    out = await provider.complete(AgentTask.SECTION_REWRITE, "Rewrite summary")
    assert out


@pytest.mark.asyncio
async def test_grok_provider_mock_when_unconfigured(monkeypatch):
    monkeypatch.setattr("apps.web.config.settings.xai_api_key", "")
    provider = GrokProvider()
    out = await provider.complete(AgentTask.VALIDATION, "Validate output")
    assert out
