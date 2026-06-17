from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from packages.agent.schemas.providers import LLMProviderName


class AgentTask(StrEnum):
    JD_ANALYSIS = "jd_analysis"
    RESUME_ANALYSIS = "resume_analysis"
    SECTION_REWRITE = "section_rewrite"
    VALIDATION = "validation"


class LLMProvider(ABC):
    name: LLMProviderName

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def model_for_task(self, task: AgentTask) -> str:
        raise NotImplementedError

    @abstractmethod
    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        raise NotImplementedError
