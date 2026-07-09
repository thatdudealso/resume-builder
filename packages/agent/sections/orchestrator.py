from __future__ import annotations

import asyncio
from typing import Any

from packages.agent.schemas.variants import (
    DEFAULT_VARIANT,
    SECTION_KEYS,
    VARIANT_ORDER,
    VariantName,
)
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


def _sections_to_tailor(state: AgentState, sources: dict[str, str]) -> list[tuple[str, str]]:
    """Tailor only sections with source content or explicitly user-added sections."""
    user_added = state.get("user_added_sections") or {}
    present = set(state.get("sections_to_tailor") or [])
    tailored: list[tuple[str, str]] = []

    for key in SECTION_KEYS:
        text = user_added.get(key) or sources.get(key, "")
        if not text.strip():
            continue
        if key in user_added or key in present or not present:
            tailored.append((key, text))
    return tailored


def _variants_to_build(state: AgentState) -> tuple[VariantName, ...]:
    selected = state.get("selected_variant") or DEFAULT_VARIANT.value
    try:
        return (VariantName(selected),)
    except ValueError:
        return (DEFAULT_VARIANT,)


def _extract_rewrite_context(
    state: AgentState,
) -> tuple[list[str], list[str], list[str]]:
    """Extract requirement gap lists and priority keywords from state for the rewrite prompt.

    Returns (missing_reqs, met_reqs, priority_keywords).
    missing_reqs: formatted strings for requirements that are missing or partial.
    met_reqs: formatted strings for requirements already demonstrated, with evidence.
    priority_keywords: JD keywords sorted by LLM-assigned weight descending.
    """
    resume_analysis: dict[str, Any] = state.get("resume_analysis") or {}
    jd_analysis: dict[str, Any] = state.get("jd_analysis") or {}

    evidence: list[dict[str, Any]] = [
        item for item in (resume_analysis.get("requirement_evidence") or [])
        if isinstance(item, dict)
    ]
    missing_reqs: list[str] = []
    met_reqs: list[str] = []

    for item in evidence:
        req = item.get("requirement", "")
        status = item.get("status", "missing")
        quote = (item.get("evidence_quote") or "").strip()
        if status == "missing":
            missing_reqs.append(
                f"[missing] {req}: no supporting evidence found in source resume"
            )
        elif status == "partial":
            hint = f" (found: '{quote[:80]}')" if quote else ""
            missing_reqs.append(
                f"[partial] {req}: mentioned but needs stronger, concrete evidence{hint}"
            )
        elif status == "met" and quote:
            met_reqs.append(f"[met] {req}: '{quote[:100]}'")

    kw_weighted: list[dict[str, Any]] = jd_analysis.get("keywords_weighted") or []
    priority_keywords = [
        kw["term"]
        for kw in sorted(kw_weighted, key=lambda k: k.get("weight", 0.0), reverse=True)
        if kw.get("term")
    ]

    return missing_reqs, met_reqs, priority_keywords


async def build_all_variants(
    state: AgentState, agent_service: AgentService
) -> dict[str, dict[str, str]]:
    sources = _source_sections(state)
    gaps = state.get("keyword_gaps") or []
    jd = state.get("jd_text", "")
    to_tailor = _sections_to_tailor(state, sources)
    missing_reqs, met_reqs, priority_kws = _extract_rewrite_context(state)

    variants: dict[str, dict[str, str]] = {}
    for variant in _variants_to_build(state):
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
                    missing_requirements=missing_reqs,
                    met_requirements=met_reqs,
                    priority_keywords=priority_kws,
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
    missing_reqs, met_reqs, priority_kws = _extract_rewrite_context(state)
    updated: dict[str, str] = {}
    for variant in VARIANT_ORDER:
        updated[variant.value] = await rewrite_section(
            section,
            content,
            variant=variant,
            jd_text=jd,
            keyword_gaps=gaps,
            missing_requirements=missing_reqs,
            met_requirements=met_reqs,
            priority_keywords=priority_kws,
            agent_service=agent_service,
        )
    return updated


def pick_variant_sections(
    variants: dict[str, dict[str, str]],
    selected: str | None = None,
) -> dict[str, str]:
    key = selected or DEFAULT_VARIANT.value
    return dict(variants.get(key, variants.get(DEFAULT_VARIANT.value, {})))
