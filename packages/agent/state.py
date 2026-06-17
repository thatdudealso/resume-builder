from __future__ import annotations

import re
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    user_id: str
    llm_provider: str
    master_resume_text: str
    master_resume_structured: dict[str, str]
    jd_text: str
    jd_keywords: list[str]
    keyword_gaps: list[str]
    jd_analysis: dict[str, Any]
    resume_analysis: dict[str, Any]
    match_score_before: dict[str, Any]
    match_score_after: dict[str, Any]
    sections_missing: list[str]
    variants: dict[str, dict[str, str]]
    selected_variant: str
    changelog: list[dict[str, str]]
    sections_editable: dict[str, dict[str, object]]
    user_section_overrides: dict[str, str]
    user_added_sections: dict[str, str]
    ats_score_before: float
    ats_score_after: float
    section_drafts: dict[str, str]
    validation_errors: list[str]
    validation_passed: bool
    retry_count: int
    final_output: dict[str, object]  # built by format_output; values are str/float/list/dict
    preview_text: str
    output_locked: bool
    cancelled: bool
    fatal_error: str


SECTION_PATTERN = re.compile(
    r"(?im)^(experience|education|skills|summary|work history|professional experience)\s*:?\s*$"
)


def split_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    sections: dict[str, list[str]] = {"summary": [], "experience": [], "skills": [], "other": []}
    current = "other"
    for line in lines:
        match = SECTION_PATTERN.match(line.strip())
        if match:
            key = match.group(1).lower()
            if "experience" in key or "work" in key or "professional" in key:
                current = "experience"
            elif "education" in key:
                current = "education"
            elif "skill" in key:
                current = "skills"
            elif "summary" in key:
                current = "summary"
            else:
                current = "other"
            continue
        sections.setdefault(current, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def extract_keywords(jd_text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,}", jd_text.lower())
    stop = {
        "and", "the", "with", "for", "you", "will", "our", "are", "this", "that", "from", "have"
    }
    freq: dict[str, int] = {}
    for w in words:
        if len(w) < 3 or w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [w for w, _ in ranked[:40]]


def score_coverage(resume_text: str, keywords: list[str]) -> tuple[float, list[str]]:
    resume_lower = resume_text.lower()
    present = [k for k in keywords if k in resume_lower]
    gaps = [k for k in keywords if k not in resume_lower]
    score = (len(present) / len(keywords) * 100) if keywords else 0.0
    return round(score, 2), gaps
