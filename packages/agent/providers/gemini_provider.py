from __future__ import annotations

import httpx

from apps.web.config import settings
from packages.agent.providers._mock import mock_complete
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.providers import LLMProviderName

_TASK_MODELS: dict[AgentTask, str] = {
    AgentTask.INPUT_ANALYSIS: "gemini-2.0-flash-lite",
    AgentTask.JD_ANALYSIS: "gemini-2.0-flash-lite",
    AgentTask.RESUME_ANALYSIS: "gemini-2.0-flash-lite",
    AgentTask.SECTION_REWRITE: "gemini-2.0-flash-lite",
    AgentTask.VALIDATION: "gemini-2.0-flash-lite",
}


class GeminiProvider(LLMProvider):
    name = LLMProviderName.GEMINI

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key)

    def model_for_task(self, task: AgentTask) -> str:
        return _TASK_MODELS[task]

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        if not self.is_configured():
            return mock_complete(task, prompt, json_mode=json_mode)

        model = self.model_for_task(task)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={settings.gemini_api_key}"
        )
        generation_config: dict[str, object] = {"maxOutputTokens": 4096}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError("Empty Gemini response")
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            raise ValueError("Empty Gemini content")
        return str(parts[0].get("text", ""))
