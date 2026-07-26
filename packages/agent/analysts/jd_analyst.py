from __future__ import annotations

import logging
from typing import Literal

from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.analysis import JDAnalysis, JDRequirement, WeightedKeyword
from packages.agent.state import extract_keywords
from packages.agent.utils.json_parse import parse_json_response

logger = logging.getLogger(__name__)

JD_ANALYST_PROMPT = """Analyze this job description and return JSON only with keys:
must_have (list of {{requirement, category}}), nice_to_have (same shape),
role_type (ic|manager|hybrid|unknown), seniority_level (junior|mid|senior|lead|executive|unknown),
responsibilities (list of strings), dealbreakers (list of strings),
keywords_weighted (list of {{term, weight}} where weight is 0-1).

Job description:
{jd_text}
"""


def fallback_jd_analysis(jd_text: str) -> JDAnalysis:
    keywords = extract_keywords(jd_text)
    requirement_terms = list(keywords)
    weighted = [
        WeightedKeyword(term=term, weight=max(0.3, 1.0 - index * 0.05))
        for index, term in enumerate(keywords[:15])
    ]
    must_have: list[JDRequirement] = []
    for term in requirement_terms[:5]:
        category: Literal["skill", "cert", "education", "years", "other"] = (
            "years" if "year" in term else "skill"
        )
        must_have.append(JDRequirement(requirement=term, category=category))
    nice_to_have = [
        JDRequirement(requirement=term, category="skill") for term in requirement_terms[5:12]
    ]
    seniority: Literal["junior", "mid", "senior", "lead", "executive", "unknown"] = "unknown"
    lowered = jd_text.lower()
    if "senior" in lowered or "sr." in lowered:
        seniority = "senior"
    elif "junior" in lowered or "jr." in lowered:
        seniority = "junior"
    elif "lead" in lowered or "principal" in lowered:
        seniority = "lead"
    elif "manager" in lowered or "director" in lowered:
        seniority = "executive"
    role_type: Literal["ic", "manager", "hybrid", "unknown"] = (
        "manager" if "manager" in lowered or "lead team" in lowered else "ic"
    )
    return JDAnalysis(
        must_have=must_have,
        nice_to_have=nice_to_have,
        role_type=role_type,
        seniority_level=seniority,
        responsibilities=[],
        dealbreakers=[],
        keywords_weighted=weighted,
    )


async def analyze_jd(jd_text: str, provider: LLMProvider) -> JDAnalysis:
    prompt = JD_ANALYST_PROMPT.format(jd_text=jd_text[:12000])
    if provider.is_configured():
        raw = None
        try:
            raw = await provider.complete(AgentTask.JD_ANALYSIS, prompt, json_mode=True)
            return JDAnalysis.model_validate(parse_json_response(raw))
        except Exception as exc:
            logger.warning(
                "analyze_jd: LLM response rejected, falling back to keyword extraction. "
                "error_type=%s",
                type(exc).__name__,
            )
    return fallback_jd_analysis(jd_text)
