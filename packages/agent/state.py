from __future__ import annotations

import re
from typing import Any, TypedDict

from packages.agent.schemas.variants import SECTION_KEYS


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
    resume_structure: dict[str, Any]
    sections_to_tailor: list[str]
    sections_suggested: list[dict[str, Any]]
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


_SECTION_ALIASES: dict[str, str] = {
    "summary": "summary",
    "objective": "summary",
    "profile": "summary",
    "about": "summary",
    "about me": "summary",
    "professional": "experience",
    "professional experience": "experience",
    "experience": "experience",
    "work history": "experience",
    "employment": "experience",
    "employment history": "experience",
    "education": "education",
    "academic": "education",
    "academic background": "education",
    "skills": "skills",
    "skill": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "technologies": "skills",
}

_SECTION_LINE_PATTERN = re.compile(
    r"(?im)^("
    r"summary|objective|profile|about(?:\s+me)?"
    r"|professional(?:\s+experience)?|experience|work\s+history|employment(?:\s+history)?"
    r"|education|academic(?:\s+background)?"
    r"|skills?|technical\s+skills|core\s+competencies|technologies"
    r")\s*:?\s*(.*)$"
)

_OTHER_SPLIT_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "experience",
        re.compile(
            r"(?im)(?:^|\n)"
            r"(?=(?:professional(?:\s+experience)?|experience|work\s+history|employment)\b)"
        ),
    ),
    ("skills", re.compile(r"(?im)(?:^|\n)(?=(?:technical\s+)?skills\b|core\s+competencies\b)")),
    ("education", re.compile(r"(?im)(?:^|\n)(?=education\b|academic(?:\s+background)?\b)")),
    ("summary", re.compile(r"(?im)(?:^|\n)(?=(?:objective|summary|profile)\b)")),
)


def _canonical_section(header: str) -> str | None:
    normalized = re.sub(r"\s+", " ", header.strip().lower())
    return _SECTION_ALIASES.get(normalized)


def _append_line(sections: dict[str, list[str]], section: str, line: str) -> None:
    if line.strip():
        sections.setdefault(section, []).append(line)


def _split_sections_raw(text: str) -> dict[str, str]:
    lines = text.splitlines()
    buckets: dict[str, list[str]] = {
        "header": [],
        "summary": [],
        "experience": [],
        "skills": [],
        "education": [],
        "other": [],
    }
    current = "header"

    for line in lines:
        match = _SECTION_LINE_PATTERN.match(line.strip())
        if match:
            canonical = _canonical_section(match.group(1))
            if canonical:
                current = canonical
                remainder = (match.group(2) or "").strip()
                if remainder:
                    _append_line(buckets, current, remainder)
                continue
        _append_line(buckets, current, line)

    return {k: "\n".join(v).strip() for k, v in buckets.items() if v}


def _redistribute_other(sections: dict[str, str]) -> dict[str, str]:
    other = sections.get("other", "").strip()
    if not other:
        return sections

    result = dict(sections)
    other_text = result.pop("other", "")
    if not other_text:
        return result

    split_at: list[tuple[int, str]] = [(0, "other")]
    for section, pattern in _OTHER_SPLIT_MARKERS:
        for match in pattern.finditer(other_text):
            split_at.append((match.start(), section))

    split_at = sorted(set(split_at), key=lambda item: item[0])
    if len(split_at) == 1:
        if not result.get("summary") and not result.get("experience"):
            result["summary"] = other_text
        else:
            result["other"] = other_text
        return result

    chunks: list[tuple[str, str]] = []
    for index, (start, section) in enumerate(split_at):
        end = split_at[index + 1][0] if index + 1 < len(split_at) else len(other_text)
        chunk = other_text[start:end].strip()
        if chunk:
            chunks.append((section, chunk))

    for section, chunk in chunks:
        cleaned = re.sub(
            r"(?im)^(?:objective|summary|profile|professional(?:\s+experience)?|"
            r"experience|work\s+history|employment|education|academic(?:\s+background)?|"
            r"skills?|technical\s+skills|core\s+competencies|technologies)\s*:?\s*",
            "",
            chunk,
            count=1,
        ).strip()
        if not cleaned:
            continue
        if result.get(section):
            result[section] = f"{result[section]}\n\n{cleaned}"
        else:
            result[section] = cleaned

    return result


def split_sections(text: str) -> dict[str, str]:
    return _redistribute_other(_split_sections_raw(text))


def structured_sections_missing(structured: dict[str, str]) -> list[str]:
    return [key for key in SECTION_KEYS if not structured.get(key, "").strip()]


def extract_keywords(jd_text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,}", jd_text.lower())
    stop = {
        "and", "the", "with", "for", "you", "will", "our", "are", "this", "that", "from", "have",
        "between", "against", "within", "across", "customer", "technical", "using",
        "their", "there", "would", "could", "should", "about",
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
