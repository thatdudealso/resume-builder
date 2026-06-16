from __future__ import annotations

from packages.agent.analysts.jd_analyst import analyze_jd
from packages.agent.analysts.resume_analyst import analyze_resume
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.providers.registry import get_provider, resolve_provider_name
from packages.agent.schemas.analysis import JDAnalysis, ResumeAnalysis
from packages.agent.schemas.match import MatchScoreResult
from packages.agent.schemas.providers import LLMProviderName
from packages.agent.scoring.match_score import compute_match_score


class AgentService:
    """Provider-routed agent service: orchestration is shared, LLM calls use one provider."""

    def __init__(self, provider_name: str | LLMProviderName) -> None:
        self.provider_name = resolve_provider_name(
            provider_name.value if isinstance(provider_name, LLMProviderName) else provider_name
        )
        self.provider: LLMProvider = get_provider(self.provider_name)

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        return await self.provider.complete(task, prompt, json_mode=json_mode)

    async def analyze_jd(self, jd_text: str) -> JDAnalysis:
        return await analyze_jd(jd_text, self.provider)

    async def analyze_resume(self, resume_text: str, jd_analysis: JDAnalysis) -> ResumeAnalysis:
        return await analyze_resume(resume_text, jd_analysis, self.provider)

    async def analyze_inputs(self, jd_text: str, resume_text: str) -> dict[str, object]:
        jd_analysis = await self.analyze_jd(jd_text)
        resume_analysis = await self.analyze_resume(resume_text, jd_analysis)
        match_before = self.score_match(jd_analysis, resume_analysis, resume_text)
        return {
            "jd_analysis": jd_analysis.model_dump(),
            "resume_analysis": resume_analysis.model_dump(),
            "match_score_before": match_before.model_dump(),
            "sections_missing": resume_analysis.sections_missing,
        }

    def score_match(
        self,
        jd_analysis: JDAnalysis | dict,
        resume_analysis: ResumeAnalysis | dict,
        resume_text: str,
    ) -> MatchScoreResult:
        jd = jd_analysis if isinstance(jd_analysis, JDAnalysis) else JDAnalysis.model_validate(jd_analysis)
        resume = (
            resume_analysis
            if isinstance(resume_analysis, ResumeAnalysis)
            else ResumeAnalysis.model_validate(resume_analysis)
        )
        return compute_match_score(jd, resume, resume_text)

    def provider_info(self) -> dict[str, str]:
        return {
            "id": self.provider_name.value,
            "rewrite_model": self.provider.model_for_task(AgentTask.SECTION_REWRITE),
            "analysis_model": self.provider.model_for_task(AgentTask.JD_ANALYSIS),
        }
