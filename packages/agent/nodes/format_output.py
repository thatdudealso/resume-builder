from __future__ import annotations

from packages.agent.state import AgentState


def format_output(state: AgentState) -> AgentState:
    drafts = state.get("section_drafts", {})
    plain = "\n\n".join(f"{k.upper()}\n{v}" for k, v in drafts.items() if v)
    final: dict[str, object] = {
        "sections": drafts,
        "plain_text": plain,
        "ats_score_before": state.get("ats_score_before"),
        "ats_score_after": state.get("ats_score_after"),
        "keywords_used": state.get("jd_keywords", []),
    }
    preview = plain[:500]
    return {**state, "final_output": final, "preview_text": preview}
