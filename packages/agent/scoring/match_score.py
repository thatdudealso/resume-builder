from __future__ import annotations

from packages.agent.schemas.analysis import JDAnalysis, ResumeAnalysis
from packages.agent.schemas.match import MatchComponentScore, MatchScoreResult
from packages.agent.state import score_coverage

_SENIORITY_RANK = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "executive": 5,
    "unknown": 2,
}

_COMPONENT_WEIGHTS = {
    "must_have": 0.35,
    "skills": 0.20,
    "experience_relevance": 0.20,
    "ats_keywords": 0.15,
    "seniority_fit": 0.10,
}


def _must_have_score(resume_analysis: ResumeAnalysis) -> tuple[float, str]:
    evidence = resume_analysis.requirement_evidence
    if not evidence:
        return 0.0, "No requirement mapping available"
    met = sum(1 for item in evidence if item.status == "met")
    partial = sum(1 for item in evidence if item.status == "partial")
    total = len(evidence)
    score = ((met + 0.5 * partial) / total) * 100 if total else 0.0
    return round(score, 2), f"{met} met, {partial} partial of {total} must-haves"


def _skills_score(jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis) -> tuple[float, str]:
    required = [item.requirement.lower() for item in jd_analysis.must_have if item.category == "skill"]
    preferred = [item.requirement.lower() for item in jd_analysis.nice_to_have if item.category == "skill"]
    if not required and not preferred:
        required = [item.term.lower() for item in jd_analysis.keywords_weighted[:8]]
    resume_skills = {skill.lower() for skill in resume_analysis.skills}
    resume_text_skills = resume_skills
    if not resume_skills:
        return 0.0, "No skills extracted"

    def has_skill(term: str) -> bool:
        return term in resume_text_skills or any(term in skill for skill in resume_text_skills)

    req_met = sum(1 for term in required if has_skill(term))
    pref_met = sum(1 for term in preferred if has_skill(term))
    req_score = (req_met / len(required)) if required else 1.0
    pref_score = (pref_met / len(preferred)) if preferred else 1.0
    score = (0.75 * req_score + 0.25 * pref_score) * 100
    return round(score, 2), f"{req_met}/{len(required) or 0} required skills matched"


def _experience_relevance_score(resume_analysis: ResumeAnalysis) -> tuple[float, str]:
    evidence = resume_analysis.requirement_evidence
    if not evidence:
        bullets = sum(len(role.bullets) for role in resume_analysis.roles)
        return (70.0 if bullets else 30.0), "Heuristic from role bullets"
    met = sum(1 for item in evidence if item.status in ("met", "partial") and item.evidence_quote)
    total = len(evidence)
    score = (met / total) * 100 if total else 0.0
    return round(score, 2), f"{met}/{total} requirements supported by evidence"


def _seniority_score(jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis) -> tuple[float, str]:
    jd_rank = _SENIORITY_RANK.get(jd_analysis.seniority_level, 2)
    resume_rank = _SENIORITY_RANK.get(resume_analysis.seniority_inferred, 2)
    diff = abs(jd_rank - resume_rank)
    score = max(0.0, 100.0 - diff * 25.0)
    return round(score, 2), f"JD {jd_analysis.seniority_level} vs resume {resume_analysis.seniority_inferred}"


def _dealbreaker_flags(jd_analysis: JDAnalysis, resume_analysis: ResumeAnalysis) -> list[str]:
    flags: list[str] = []
    missing = {item.requirement.lower() for item in resume_analysis.requirement_evidence if item.status == "missing"}
    for breaker in jd_analysis.dealbreakers:
        if breaker.lower() in missing or breaker.lower() in {m.lower() for m in resume_analysis.sections_missing}:
            flags.append(breaker)
    return flags


def compute_match_score(
    jd_analysis: JDAnalysis,
    resume_analysis: ResumeAnalysis,
    resume_text: str,
) -> MatchScoreResult:
    keywords = [item.term for item in jd_analysis.keywords_weighted]
    if not keywords:
        keywords = [item.requirement for item in jd_analysis.must_have]
    ats_score, _gaps = score_coverage(resume_text, [k.lower() for k in keywords])

    must_score, must_detail = _must_have_score(resume_analysis)
    skills_score, skills_detail = _skills_score(jd_analysis, resume_analysis)
    exp_score, exp_detail = _experience_relevance_score(resume_analysis)
    seniority_score, seniority_detail = _seniority_score(jd_analysis, resume_analysis)

    components = [
        MatchComponentScore(name="must_have", score=must_score, weight=_COMPONENT_WEIGHTS["must_have"], detail=must_detail),
        MatchComponentScore(name="skills", score=skills_score, weight=_COMPONENT_WEIGHTS["skills"], detail=skills_detail),
        MatchComponentScore(
            name="experience_relevance",
            score=exp_score,
            weight=_COMPONENT_WEIGHTS["experience_relevance"],
            detail=exp_detail,
        ),
        MatchComponentScore(
            name="ats_keywords",
            score=ats_score,
            weight=_COMPONENT_WEIGHTS["ats_keywords"],
            detail=f"{ats_score}% keyword coverage",
        ),
        MatchComponentScore(
            name="seniority_fit",
            score=seniority_score,
            weight=_COMPONENT_WEIGHTS["seniority_fit"],
            detail=seniority_detail,
        ),
    ]

    overall = round(sum(c.score * c.weight for c in components), 2)
    flags = _dealbreaker_flags(jd_analysis, resume_analysis)
    penalty = min(overall, len(flags) * 25.0)
    overall = max(0.0, round(overall - penalty, 2))

    evidence = resume_analysis.requirement_evidence
    quoted = sum(1 for item in evidence if item.evidence_quote.strip())
    evidence_pct = round((quoted / len(evidence)) * 100, 2) if evidence else 0.0

    return MatchScoreResult(
        overall=overall,
        components=components,
        dealbreaker_flags=flags,
        evidence_coverage_pct=evidence_pct,
    )
