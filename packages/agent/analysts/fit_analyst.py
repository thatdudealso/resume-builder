from __future__ import annotations

from typing import Literal, cast

from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.fit_assessment import FitAssessment
from packages.agent.utils.json_parse import parse_json_response

_FIT_ASSESSMENT_PROMPT = """You are a career coach reviewing a tailored resume against a job
description.
Structured analysis is already done — synthesise a verdict and actionable coaching bullets.

JD must-have requirements: {must_have}
JD nice-to-have requirements: {nice_to_have}
Seniority expected by JD: {seniority_level}
Seniority inferred from resume: {seniority_inferred}
Requirement evidence (requirement=status): {requirement_evidence}
Match score before tailoring: {score_before}
Match score after tailoring: {score_after}
Score component breakdown: {components}
Dealbreakers flagged: {dealbreakers}

Return JSON only with exactly these two keys:
"verdict": one of "Strong fit", "Moderate fit", "Not a fit"
  - "Strong fit" if score_after >= 72 and no unmet dealbreakers
  - "Not a fit" if score_after < 45 or a dealbreaker is unmet
  - "Moderate fit" otherwise

"coaching_bullets": a list of 4-6 short, specific, actionable strings.
Each bullet must do exactly one of:
  - Name a specific missing must-have requirement and how to address it in the resume
  - Name a strength to keep prominent (what the resume already does well)
  - Warn about a dealbreaker or critically low-evidence requirement
  - Suggest a concrete phrasing or terminology change to match the JD language
Do NOT restate the score. Reference actual requirement/skill names. Be specific and direct.
"""


FitVerdict = Literal["Strong fit", "Moderate fit", "Not a fit"]


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, str | int | float):
        return float(value)
    return default


def _join(items: list[dict[str, object]], key: str = "requirement") -> str:
    return "; ".join(str(i.get(key, "")) for i in items) or "none"


def _evidence_summary(evidence: list[dict[str, object]]) -> str:
    return "; ".join(
        f"{e.get('requirement', '')}={e.get('status', 'missing')}" for e in evidence
    ) or "none"


def _components_summary(components: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for component in components:
        score = _to_float(component.get("score"))
        parts.append(f"{component.get('name', '')}={score:.0f}")
    return "; ".join(parts) or "none"


def _fallback(
    score_after: float,
    evidence: list[dict[str, object]],
    dealbreakers: list[str],
) -> FitAssessment:
    verdict: FitVerdict
    if dealbreakers:
        verdict = "Not a fit"
    elif score_after >= 72:
        verdict = "Strong fit"
    elif score_after >= 45:
        verdict = "Moderate fit"
    else:
        verdict = "Not a fit"

    bullets: list[str] = []
    if dealbreakers:
        for db in dealbreakers[:2]:
            bullets.append(f"Critical gap — dealbreaker requirement not met: {db}")
    missing = [str(e["requirement"]) for e in evidence if e.get("status") == "missing"]
    for req in missing[:3]:
        bullets.append(f"Missing requirement: add evidence for '{req}' if applicable")
    met = [str(e["requirement"]) for e in evidence if e.get("status") == "met"]
    if met:
        bullets.append(f"Strong evidence already present for: {', '.join(met[:2])}")
    if not bullets:
        bullets.append("Resume covers the core requirements — review keyword alignment for ATS.")
    return FitAssessment(verdict=verdict, coaching_bullets=bullets[:6])


async def assess_fit(
    jd_analysis: dict[str, object],
    resume_analysis: dict[str, object],
    match_score: dict[str, object],
    provider: LLMProvider,
) -> FitAssessment:
    current = cast(dict[str, object], match_score.get("current") or {})
    previous = cast(dict[str, object], match_score.get("previous") or {})
    score_after = _to_float(current.get("overall"))
    evidence = cast(list[dict[str, object]], resume_analysis.get("requirement_evidence") or [])
    dealbreakers = cast(list[str], current.get("dealbreaker_flags") or [])

    if provider.is_configured():
        prompt = _FIT_ASSESSMENT_PROMPT.format(
            must_have=_join(cast(list[dict[str, object]], jd_analysis.get("must_have") or [])),
            nice_to_have=_join(
                cast(list[dict[str, object]], jd_analysis.get("nice_to_have") or [])
            ),
            seniority_level=jd_analysis.get("seniority_level", "unknown"),
            seniority_inferred=resume_analysis.get("seniority_inferred", "unknown"),
            requirement_evidence=_evidence_summary(evidence),
            score_before=f"{_to_float(previous.get('overall')):.1f}",
            score_after=f"{score_after:.1f}",
            components=_components_summary(
                cast(list[dict[str, object]], current.get("components") or [])
            ),
            dealbreakers="; ".join(dealbreakers) or "none",
        )
        try:
            raw = await provider.complete(AgentTask.FIT_ASSESSMENT, prompt, json_mode=True)
            data = parse_json_response(raw)
            return FitAssessment.model_validate(data)
        except Exception:
            pass

    return _fallback(score_after, evidence, dealbreakers)
