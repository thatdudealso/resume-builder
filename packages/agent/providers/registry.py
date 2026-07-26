from __future__ import annotations

from packages.agent.providers.anthropic_provider import AnthropicProvider
from packages.agent.providers.base import LLMProvider
from packages.agent.providers.gemini_provider import GeminiProvider
from packages.agent.providers.grok_provider import GrokProvider
from packages.agent.providers.openai_provider import OpenAIProvider
from packages.agent.schemas.providers import DEFAULT_PROVIDER, PROVIDER_LABELS, LLMProviderName

_PROVIDER_FACTORIES: dict[LLMProviderName, type[LLMProvider]] = {
    LLMProviderName.OPENAI: OpenAIProvider,
    LLMProviderName.ANTHROPIC: AnthropicProvider,
    LLMProviderName.GEMINI: GeminiProvider,
    LLMProviderName.GROK: GrokProvider,
}


def get_provider(name: str | LLMProviderName) -> LLMProvider:
    try:
        provider_name = LLMProviderName(name)
    except ValueError as exc:
        raise ValueError(f"Unknown LLM provider: {name}") from exc
    return _PROVIDER_FACTORIES[provider_name]()


def list_provider_options() -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for provider_name in LLMProviderName:
        provider = get_provider(provider_name)
        options.append(
            {
                "id": provider_name.value,
                "label": PROVIDER_LABELS[provider_name],
                "configured": provider.is_configured(),
                "is_default": provider_name == DEFAULT_PROVIDER,
            }
        )
    return options


def resolve_provider_name(name: str | None) -> LLMProviderName:
    if not name:
        return DEFAULT_PROVIDER
    try:
        return LLMProviderName(name)
    except ValueError:
        return DEFAULT_PROVIDER
