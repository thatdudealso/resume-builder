from __future__ import annotations

from packages.agent.providers.registry import resolve_provider_name
from packages.agent.schemas.providers import DEFAULT_PROVIDER, LLMProviderName


def test_default_provider_is_openai():
    assert DEFAULT_PROVIDER == LLMProviderName.OPENAI


def test_resolve_provider_name_falls_back_to_default_for_legacy_huggingface():
    assert resolve_provider_name("huggingface") == LLMProviderName.OPENAI


def test_resolve_provider_name_falls_back_to_default_for_unknown_value():
    assert resolve_provider_name("not-a-real-provider") == DEFAULT_PROVIDER
