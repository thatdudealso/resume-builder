from __future__ import annotations

import pytest

from packages.agent.providers.registry import (
    get_provider,
    list_provider_options,
    resolve_provider_name,
)
from packages.agent.schemas.providers import DEFAULT_PROVIDER, LLMProviderName


def test_list_provider_options_includes_all_providers():
    options = list_provider_options()
    ids = {item["id"] for item in options}
    assert ids == {p.value for p in LLMProviderName}


def test_get_provider_openai():
    provider = get_provider("openai")
    assert provider.name == LLMProviderName.OPENAI


def test_resolve_provider_defaults():
    assert resolve_provider_name(None) == DEFAULT_PROVIDER


def test_get_provider_unknown():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_provider("not-a-provider")
