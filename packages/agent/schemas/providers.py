from __future__ import annotations

from enum import StrEnum


class LLMProviderName(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROK = "grok"
    HUGGINGFACE = "huggingface"


PROVIDER_LABELS: dict[LLMProviderName, str] = {
    LLMProviderName.OPENAI: "OpenAI",
    LLMProviderName.ANTHROPIC: "Anthropic",
    LLMProviderName.GEMINI: "Google Gemini",
    LLMProviderName.GROK: "xAI Grok",
    LLMProviderName.HUGGINGFACE: "Hugging Face",
}

DEFAULT_PROVIDER = LLMProviderName.HUGGINGFACE
