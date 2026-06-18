from __future__ import annotations

from packages.agent.providers.anthropic_provider import AnthropicProvider
from packages.agent.providers.base import AgentTask
from packages.agent.providers.gemini_provider import GeminiProvider
from packages.agent.providers.grok_provider import GrokProvider
from packages.agent.providers.huggingface_provider import HuggingFaceProvider
from packages.agent.providers.openai_provider import OpenAIProvider


def test_openai_uses_fast_models():
    provider = OpenAIProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == "gpt-4o-mini"


def test_anthropic_uses_fast_models():
    provider = AnthropicProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == "claude-3-5-haiku-20241022"


def test_gemini_uses_fast_models():
    provider = GeminiProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == "gemini-2.0-flash-lite"


def test_grok_uses_fast_models():
    provider = GrokProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == "grok-2-mini"


def test_huggingface_uses_fast_models():
    provider = HuggingFaceProvider()
    for task in AgentTask:
        assert provider.model_for_task(task) == "meta-llama/Llama-3.1-8B-Instruct"
