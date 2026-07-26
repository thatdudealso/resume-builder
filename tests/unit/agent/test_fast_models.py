from __future__ import annotations

from packages.agent.providers.anthropic_provider import ANTHROPIC_OPUS_MODEL, AnthropicProvider
from packages.agent.providers.base import AgentTask
from packages.agent.providers.gemini_provider import GEMINI_FLASH_MODEL, GeminiProvider
from packages.agent.providers.grok_provider import GROK_MODEL, GrokProvider
from packages.agent.providers.openai_provider import OpenAIProvider


def _all_tasks_have_models(provider_cls) -> None:
    provider = provider_cls()
    for task in AgentTask:
        model = provider.model_for_task(task)
        assert model and isinstance(model, str), f"No model for {task}"


def _rewrite_uses_quality_model(provider_cls, quality_model: str) -> None:
    provider = provider_cls()
    assert provider.model_for_task(AgentTask.SECTION_REWRITE) == quality_model


def _analysis_uses_fast_model(provider_cls, fast_model: str) -> None:
    provider = provider_cls()
    for task in [AgentTask.INPUT_ANALYSIS, AgentTask.JD_ANALYSIS, AgentTask.RESUME_ANALYSIS]:
        assert provider.model_for_task(task) == fast_model, f"Expected {fast_model} for {task}"


def test_all_providers_cover_all_tasks():
    providers = [
        AnthropicProvider,
        OpenAIProvider,
        GeminiProvider,
        GrokProvider,
    ]
    for cls in providers:
        _all_tasks_have_models(cls)


def test_anthropic_uses_opus():
    provider = AnthropicProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == ANTHROPIC_OPUS_MODEL


def test_openai_model_tiers():
    _rewrite_uses_quality_model(OpenAIProvider, "gpt-4o")
    _analysis_uses_fast_model(OpenAIProvider, "gpt-4o-mini")


def test_gemini_uses_flash():
    provider = GeminiProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == GEMINI_FLASH_MODEL


def test_grok_uses_latest():
    provider = GrokProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == GROK_MODEL
