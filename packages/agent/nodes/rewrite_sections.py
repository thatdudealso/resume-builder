from __future__ import annotations

import re

from packages.agent.state import AgentState, score_coverage


async def rewrite_sections(state: AgentState, llm_complete) -> AgentState:
    structured = state.get("master_resume_structured", {})
    gaps = state.get("keyword_gaps", [])
    jd = state.get("jd_text", "")
    drafts = dict(state.get("section_drafts", structured))
    prompt = (
        "Rewrite the resume sections to naturally include these missing JD keywords "
        f"without inventing new employers, dates, or achievements.\n"
        f"Keywords: {', '.join(gaps[:20])}\n"
        f"Job description:\n{jd}\n"
        f"Resume sections JSON:\n{drafts}\n"
        "Return only valid JSON with the same section keys."
    )
    response = await llm_complete(
        model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        prompt=prompt,
        node="rewrite_sections",
    )
    import json

    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            drafts.update({k: str(v) for k, v in parsed.items()})
    except json.JSONDecodeError:
        drafts["summary"] = response[:2000]
    after, _ = score_coverage("\n".join(drafts.values()), state.get("jd_keywords", []))
    return {**state, "section_drafts": drafts, "ats_score_after": after}
