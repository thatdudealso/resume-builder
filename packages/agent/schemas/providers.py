from __future__ import annotations

from enum import StrEnum


class LLMProviderName(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROK = "grok"


PROVIDER_LABELS: dict[LLMProviderName, str] = {
    LLMProviderName.OPENAI: "OpenAI",
    LLMProviderName.ANTHROPIC: "Anthropic",
    LLMProviderName.GEMINI: "Google Gemini",
    LLMProviderName.GROK: "xAI Grok",
}

DEFAULT_PROVIDER = LLMProviderName.OPENAI
