from __future__ import annotations

import anthropic

from apps.web.config import settings
from packages.agent.providers._mock import mock_complete
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.providers import LLMProviderName

ANTHROPIC_OPUS_MODEL = "claude-opus-4-8"

_TASK_MODELS: dict[AgentTask, str] = {
    AgentTask.RESUME_ORCHESTRATION: ANTHROPIC_OPUS_MODEL,
    AgentTask.INPUT_ANALYSIS: ANTHROPIC_OPUS_MODEL,
    AgentTask.JD_ANALYSIS: ANTHROPIC_OPUS_MODEL,
    AgentTask.RESUME_ANALYSIS: ANTHROPIC_OPUS_MODEL,
    AgentTask.SECTION_REWRITE: ANTHROPIC_OPUS_MODEL,
    AgentTask.VALIDATION: ANTHROPIC_OPUS_MODEL,
}


class AnthropicProvider(LLMProvider):
    name = LLMProviderName.ANTHROPIC

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def model_for_task(self, task: AgentTask) -> str:
        return _TASK_MODELS[task]

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        if not self.is_configured():
            return mock_complete(task, prompt, json_mode=json_mode)

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        system = "Respond with valid JSON only." if json_mode else None
        create_kwargs: dict[str, object] = {
            "model": self.model_for_task(task),
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system is not None:
            create_kwargs["system"] = system
        msg = await client.messages.create(**create_kwargs)  # type: ignore[call-overload]
        block = msg.content[0]
        if hasattr(block, "text"):
            return str(block.text)
        return str(block)
