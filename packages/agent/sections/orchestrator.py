from __future__ import annotations

import asyncio

from packages.agent.schemas.variants import DEFAULT_VARIANT, SECTION_KEYS, VARIANT_ORDER, VariantName
from packages.agent.sections.agent import rewrite_section
from packages.agent.service import AgentService
from packages.agent.state import AgentState


def _source_sections(state: AgentState) -> dict[str, str]:
    structured = state.get("master_resume_structured") or {}
    drafts = state.get("section_drafts") or {}
    user_added = state.get("user_added_sections") or {}
    sources: dict[str, str] = {}
    for key in SECTION_KEYS:
        sources[key] = user_added.get(key) or drafts.get(key) or structured.get(key) or ""
    return sources


def _sections_to_tailor(
    sources: dict[str, str],
    missing: list[str],
    user_added: dict[str, str],
) -> list[tuple[str, str]]:
    tailored: list[tuple[str, str]] = []
    for key in SECTION_KEYS:
        if key in missing and key not in user_added:
            continue
        text = user_added.get(key) or sources.get(key, "")
        if text.strip():
            tailored.append((key, text))
    return tailored


async def build_all_variants(state: AgentState, agent_service: AgentService) -> dict[str, dict[str, str]]:
    sources = _source_sections(state)
    missing = state.get("sections_missing") or []
    user_added = state.get("user_added_sections") or {}
    gaps = state.get("keyword_gaps") or []
    jd = state.get("jd_text", "")
    to_tailor = _sections_to_tailor(sources, missing, user_added)

    variants: dict[str, dict[str, str]] = {}
    for variant in VARIANT_ORDER:
        if not to_tailor:
            variants[variant.value] = {}
            continue
        results = await asyncio.gather(
            *[
                rewrite_section(
                    section,
                    text,
                    variant=variant,
                    jd_text=jd,
                    keyword_gaps=gaps,
                    agent_service=agent_service,
                )
                for section, text in to_tailor
            ]
        )
        variants[variant.value] = {
            section: result for (section, _), result in zip(to_tailor, results, strict=True)
        }
    return variants


async def retailor_section(
    state: AgentState,
    agent_service: AgentService,
    section: str,
    content: str,
) -> dict[str, str]:
    gaps = state.get("keyword_gaps") or []
    jd = state.get("jd_text", "")
    updated: dict[str, str] = {}
    for variant in VARIANT_ORDER:
        updated[variant.value] = await rewrite_section(
            section,
            content,
            variant=variant,
            jd_text=jd,
            keyword_gaps=gaps,
            agent_service=agent_service,
        )
    return updated


def pick_variant_sections(
    variants: dict[str, dict[str, str]],
    selected: str | None = None,
) -> dict[str, str]:
    key = selected or DEFAULT_VARIANT.value
    return dict(variants.get(key, variants.get(DEFAULT_VARIANT.value, {})))
