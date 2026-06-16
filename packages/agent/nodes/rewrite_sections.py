from __future__ import annotations

from packages.agent.schemas.variants import DEFAULT_VARIANT
from packages.agent.sections.orchestrator import build_all_variants, pick_variant_sections
from packages.agent.service import AgentService
from packages.agent.state import AgentState, score_coverage


async def rewrite_sections(state: AgentState, agent_service: AgentService) -> AgentState:
    variants = await build_all_variants(state, agent_service)
    selected = state.get("selected_variant") or DEFAULT_VARIANT.value
    drafts = pick_variant_sections(variants, selected)
    after, _ = score_coverage("\n".join(drafts.values()), state.get("jd_keywords", []))
    return {
        **state,
        "variants": variants,
        "selected_variant": selected,
        "section_drafts": drafts,
        "ats_score_after": after,
    }
