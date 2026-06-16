from __future__ import annotations

from apps.web.config import settings
from packages.agent.providers._http import openai_compatible_chat
from packages.agent.providers._mock import mock_complete
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.providers import LLMProviderName

_TASK_MODELS: dict[AgentTask, str] = {
    AgentTask.JD_ANALYSIS: "grok-2-1212",
    AgentTask.RESUME_ANALYSIS: "grok-2-1212",
    AgentTask.SECTION_REWRITE: "grok-2-1212",
    AgentTask.VALIDATION: "grok-2-1212",
}


class GrokProvider(LLMProvider):
    name = LLMProviderName.GROK

    def is_configured(self) -> bool:
        return bool(settings.xai_api_key)

    def model_for_task(self, task: AgentTask) -> str:
        return _TASK_MODELS[task]

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        if not self.is_configured():
            return mock_complete(task, prompt, json_mode=json_mode)
        return await openai_compatible_chat(
            base_url=settings.xai_base_url,
            api_key=settings.xai_api_key,
            model=self.model_for_task(task),
            prompt=prompt,
            json_mode=json_mode,
        )
