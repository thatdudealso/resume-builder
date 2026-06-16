from __future__ import annotations

from packages.agent.analysts.jd_analyst import fallback_jd_analysis
from packages.agent.state import split_sections
from packages.agent.utils.json_parse import parse_json_response

_SECTION_KEYS = ("summary", "experience", "skills", "education")


def fallback_resume_analysis(resume_text: str, jd_analysis: JDAnalysis | None = None) -> ResumeAnalysis:
    sections = split_sections(resume_text)
    sections_present = {key: bool(sections.get(key, "").strip()) for key in _SECTION_KEYS}
    sections_missing = [key for key, present in sections_present.items() if not present]

    skills_blob = sections.get("skills", "")
    skills = [s.strip() for s in skills_blob.replace("\n", ",").split(",") if s.strip()]

    evidence: list[RequirementEvidence] = []
    if jd_analysis:
        lowered = resume_text.lower()
        for req in jd_analysis.must_have:
            term = req.requirement.lower()
            if term in lowered:
                evidence.append(
                    RequirementEvidence(
                        requirement=req.requirement,
                        status="met",
                        evidence_quote=req.requirement,
                    )
                )
            else:
                evidence.append(
                    RequirementEvidence(
                        requirement=req.requirement,
                        status="missing",
                        evidence_quote="",
                    )
                )

    experience = sections.get("experience", "")
    roles: list[ResumeRole] = []
    if experience:
        roles.append(ResumeRole(title="Experience", company="", dates="", bullets=experience.splitlines()[:8]))

    return ResumeAnalysis(
        sections_present=sections_present,
        sections_missing=sections_missing,
        seniority_inferred="unknown",
        roles=roles,
        skills=skills[:30],
        education=[sections.get("education", "")] if sections.get("education") else [],
        requirement_evidence=evidence,
    )


RESUME_ANALYST_PROMPT = """Analyze this resume text and return JSON only with keys:
sections_present ({summary, experience, skills, education booleans}),
sections_missing (list of section names that are absent),
seniority_inferred (junior|mid|senior|lead|executive|unknown),
roles (list of {title, company, dates, bullets}),
skills (list of strings),
education (list of strings),
requirement_evidence (list of {requirement, status: met|partial|missing, evidence_quote}).

Must-have requirements from JD:
{must_have}

Resume:
{resume_text}
"""


async def analyze_resume(
    resume_text: str,
    jd_analysis: JDAnalysis,
    provider: LLMProvider,
) -> ResumeAnalysis:
    must_have = "\n".join(f"- {item.requirement}" for item in jd_analysis.must_have[:20])
    prompt = RESUME_ANALYST_PROMPT.format(
        must_have=must_have or "- General fit",
        resume_text=resume_text[:12000],
    )
    if provider.is_configured():
        try:
            raw = await provider.complete(AgentTask.RESUME_ANALYSIS, prompt, json_mode=True)
            return ResumeAnalysis.model_validate(parse_json_response(raw))
        except Exception:
            pass
    return fallback_resume_analysis(resume_text, jd_analysis)
