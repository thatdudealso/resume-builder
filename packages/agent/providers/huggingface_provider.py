from __future__ import annotations

from packages.agent.providers._mock import mock_complete
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.providers import LLMProviderName
from packages.integrations.hf_inference import complete as hf_complete

_TASK_MODELS: dict[AgentTask, str] = {
    AgentTask.RESUME_ORCHESTRATION: "meta-llama/Llama-3.1-8B-Instruct",
    AgentTask.INPUT_ANALYSIS: "meta-llama/Llama-3.1-8B-Instruct",
    AgentTask.JD_ANALYSIS: "meta-llama/Llama-3.1-8B-Instruct",
    AgentTask.RESUME_ANALYSIS: "meta-llama/Llama-3.1-8B-Instruct",
    AgentTask.SECTION_REWRITE: "meta-llama/Llama-3.1-8B-Instruct",
    AgentTask.VALIDATION: "meta-llama/Llama-3.1-8B-Instruct",
}


class HuggingFaceProvider(LLMProvider):
    name = LLMProviderName.HUGGINGFACE

    def is_configured(self) -> bool:
        return True

    def model_for_task(self, task: AgentTask) -> str:
        return _TASK_MODELS[task]

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        node = task.value
        try:
            return await hf_complete(
                model=self.model_for_task(task),
                prompt=prompt,
                node=node,
            )
        except Exception:
            return mock_complete(task, prompt, json_mode=json_mode)
