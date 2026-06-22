from __future__ import annotations

from packages.agent.changelog.builder import build_changelog, build_sections_editable
from packages.agent.schemas.variants import DEFAULT_VARIANT, SECTION_KEYS, VARIANT_ORDER
from packages.agent.service import AgentService
from packages.agent.state import AgentState, split_sections


def _plain_text(sections: dict[str, str], *, header: str = "") -> str:
    parts: list[str] = []
    if header.strip():
        parts.append(header.strip())
    parts.extend(
        f"{key.upper()}\n{sections[key]}" for key in SECTION_KEYS if sections.get(key, "").strip()
    )
    return "\n\n".join(parts)


def format_output(state: AgentState, agent_service: AgentService | None = None) -> AgentState:
    variants = state.get("variants") or {}
    selected = state.get("selected_variant") or DEFAULT_VARIANT.value
    original_sections = state.get("master_resume_structured") or split_sections(
        state.get("master_resume_text", "")
    )
    overrides = state.get("user_section_overrides") or {}
    header = original_sections.get("header", "")

    variant_payload: dict[str, dict[str, object]] = {}
    for variant in VARIANT_ORDER:
        if variant.value not in variants:
            continue
        sections = dict(variants.get(variant.value, {}))
        for section, override in overrides.items():
            if override:
                sections[section] = override
        plain = _plain_text(sections, header=header)
        match_after = None
        if agent_service and state.get("jd_analysis") and state.get("resume_analysis"):
            match_after = agent_service.score_match(
                state["jd_analysis"],
                state["resume_analysis"],
                plain,
            ).model_dump()
        variant_payload[variant.value] = {
            "sections": sections,
            "plain_text": plain,
            "match_score": match_after,
        }

    selected_sections = dict(variant_payload.get(selected, {}).get("sections", {}))
    if not selected_sections:
        selected_sections = state.get("section_drafts") or {}
    plain = _plain_text(selected_sections, header=header)

    changelog = state.get("changelog") or build_changelog(original_sections, variants)
    sections_editable = state.get("sections_editable") or build_sections_editable(
        original_sections, variants, overrides
    )

    match_before = state.get("match_score_before") or {}
    selected_match = variant_payload.get(selected, {}).get("match_score") or {}
    match_after_dict = selected_match if isinstance(selected_match, dict) else {}

    final: dict[str, object] = {
        "sections": selected_sections,
        "plain_text": plain,
        "variants": variant_payload,
        "selected_variant": selected,
        "changelog": changelog,
        "sections_editable": sections_editable,
        "ats_score_before": state.get("ats_score_before"),
        "ats_score_after": match_after_dict.get("overall", state.get("ats_score_after")),
        "keywords_used": state.get("jd_keywords", []),
        "llm_provider": state.get("llm_provider"),
        "match_score": {
            "previous": match_before,
            "current": match_after_dict,
            "previous_overall": match_before.get("overall"),
            "current_overall": match_after_dict.get("overall"),
        },
        "sections_missing": state.get("sections_missing", []),
        "sections_suggested": state.get("sections_suggested", []),
        "resume_structure": state.get("resume_structure"),
        "jd_analysis": state.get("jd_analysis"),
        "resume_analysis": state.get("resume_analysis"),
    }
    preview = plain[:500]
    return {
        **state,
        "final_output": final,
        "preview_text": preview,
        "changelog": changelog,
        "sections_editable": sections_editable,
        "match_score_after": match_after_dict,
        "ats_score_after": match_after_dict.get("overall", state.get("ats_score_after")),
    }
