from __future__ import annotations

import logging

from packages.agent.analysts.jd_analyst import analyze_jd, fallback_jd_analysis
from packages.agent.analysts.resume_analyst import analyze_resume, fallback_resume_analysis
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.analysis import JDAnalysis, ResumeAnalysis
from packages.agent.utils.json_parse import parse_json_response

logger = logging.getLogger(__name__)

COMBINED_INPUT_PROMPT = """Analyze the job description and resume together in one pass.
Return JSON only with top-level keys ``jd_analysis`` and ``resume_analysis``.

``jd_analysis`` keys:
must_have (list of {{requirement, category}}), nice_to_have (same shape),
role_type (ic|manager|hybrid|unknown), seniority_level (junior|mid|senior|lead|executive|unknown),
responsibilities (list of strings), dealbreakers (list of strings),
keywords_weighted (list of {{term, weight}} where weight is 0-1).

``resume_analysis`` keys:
sections_present ({{summary, experience, skills, education booleans}}),
sections_missing (list of section names that are absent),
seniority_inferred (junior|mid|senior|lead|executive|unknown),
roles (list of {{title, company, dates, bullets}}),
skills (list of strings),
education (list of strings),
requirement_evidence (list of {{requirement, status: met|partial|missing, evidence_quote}})
using must-have requirements from your JD analysis.

Job description:
{jd_text}

Resume:
{resume_text}
"""


async def analyze_inputs_combined(
    jd_text: str,
    resume_text: str,
    provider: LLMProvider,
) -> tuple[JDAnalysis, ResumeAnalysis]:
    prompt = COMBINED_INPUT_PROMPT.format(
        jd_text=jd_text[:12000],
        resume_text=resume_text[:12000],
    )
    if provider.is_configured():
        raw = None
        try:
            raw = await provider.complete(AgentTask.INPUT_ANALYSIS, prompt, json_mode=True)
            data = parse_json_response(raw)
            jd_analysis = JDAnalysis.model_validate(data["jd_analysis"])
            resume_analysis = ResumeAnalysis.model_validate(data["resume_analysis"])
            return jd_analysis, resume_analysis
        except Exception as exc:
            logger.warning(
                "analyze_inputs_combined: LLM response rejected, falling back to keyword "
                "extraction. error_type=%s",
                type(exc).__name__,
            )
    jd_analysis = fallback_jd_analysis(jd_text)
    resume_analysis = fallback_resume_analysis(resume_text, jd_analysis)
    return jd_analysis, resume_analysis


async def analyze_inputs_sequential(
    jd_text: str,
    resume_text: str,
    provider: LLMProvider,
) -> tuple[JDAnalysis, ResumeAnalysis]:
    jd_analysis = await analyze_jd(jd_text, provider)
    resume_analysis = await analyze_resume(resume_text, jd_analysis, provider)
    return jd_analysis, resume_analysis
