from __future__ import annotations

from packages.agent.state import AgentState, extract_keywords, score_coverage, split_sections
from packages.core.security.sanitization import sanitize_text


def prepare_inputs(state: AgentState) -> AgentState:
    text = sanitize_text(state.get("master_resume_text", ""))
    jd = sanitize_text(state.get("jd_text", ""))
    if len(text) < 50:
        return {**state, "fatal_error": "Resume text too short"}
    if len(jd) < 20:
        return {**state, "fatal_error": "Job description too short"}
    structured = split_sections(text)
    keywords = extract_keywords(jd)
    before, gaps = score_coverage(text, keywords)
    return {
        **state,
        "master_resume_structured": structured,
        "jd_keywords": keywords,
        "keyword_gaps": gaps,
        "ats_score_before": before,
        "section_drafts": dict(structured),
        "retry_count": state.get("retry_count", 0),
        "validation_errors": [],
        "validation_passed": False,
    }
