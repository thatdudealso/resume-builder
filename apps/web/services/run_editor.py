from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.agent.changelog.builder import build_sections_editable
from packages.agent.nodes.format_output import format_output
from packages.agent.schemas.variants import DEFAULT_VARIANT, SECTION_KEYS, VARIANT_ORDER, VariantName
from packages.agent.sections.orchestrator import retailor_section
from packages.agent.service import AgentService
from packages.agent.state import split_sections
from packages.core.security.sanitization import sanitize_text
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume


def _plain_text(sections: dict[str, str]) -> str:
    return "\n\n".join(f"{key.upper()}\n{sections[key]}" for key in SECTION_KEYS if sections.get(key))


def _rebuild_final_output(
    run: AgentRun,
    resume: MasterResume,
    agent_service: AgentService,
    *,
    selected_variant: str,
    variants: dict[str, dict[str, str]],
    overrides: dict[str, str],
    missing: list[str],
) -> dict:
    original_sections = split_sections(resume.raw_text)
    state = {
        "master_resume_text": resume.raw_text,
        "master_resume_structured": original_sections,
        "jd_text": run.jd_text,
        "jd_analysis": (run.final_output or {}).get("jd_analysis"),
        "resume_analysis": (run.final_output or {}).get("resume_analysis"),
        "match_score_before": (run.final_output or {}).get("match_score", {}).get("previous"),
        "sections_missing": missing,
        "variants": variants,
        "selected_variant": selected_variant,
        "user_section_overrides": overrides,
        "jd_keywords": (run.final_output or {}).get("keywords_used", []),
    }
    formatted = format_output(state, agent_service)
    return formatted["final_output"]


async def select_variant(session: AsyncSession, run: AgentRun, variant: str) -> dict:
    try:
        VariantName(variant)
    except ValueError as exc:
        raise ValueError("Invalid variant") from exc
    final = deepcopy(run.final_output or {})
    final["selected_variant"] = variant
    variants = final.get("variants") or {}
    selected = variants.get(variant, {})
    sections = dict(selected.get("sections", {}))
    overrides = {
        section: data.get("user_override")
        for section, data in (final.get("sections_editable") or {}).items()
        if data.get("user_override")
    }
    for section, override in overrides.items():
        if override:
            sections[section] = str(override)
    final["sections"] = sections
    final["plain_text"] = _plain_text(sections)
    run.final_output = final
    await session.commit()
    return final


async def update_section_override(
    session: AsyncSession,
    run: AgentRun,
    resume: MasterResume,
    *,
    section: str,
    content: str,
) -> dict:
    if section not in SECTION_KEYS:
        raise ValueError("Invalid section")
    final = deepcopy(run.final_output or {})
    editable = final.get("sections_editable") or {}
    if section not in editable:
        editable[section] = {
            "original": split_sections(resume.raw_text).get(section, ""),
            "proposed_by_variant": {},
            "user_override": None,
        }
    editable[section]["user_override"] = sanitize_text(content)
    final["sections_editable"] = editable

    selected = final.get("selected_variant", DEFAULT_VARIANT.value)
    sections = dict((final.get("variants") or {}).get(selected, {}).get("sections", {}))
    sections[section] = sanitize_text(content)
    final["sections"] = sections
    final["plain_text"] = _plain_text(sections)
    run.final_output = final
    await session.commit()
    return final


async def add_section_and_retailor(
    session: AsyncSession,
    run: AgentRun,
    resume: MasterResume,
    *,
    section: str,
    content: str,
) -> dict:
    if section not in SECTION_KEYS:
        raise ValueError("Invalid section")
    agent_service = AgentService(run.llm_provider)
    final = deepcopy(run.final_output or {})
    missing = list(final.get("sections_missing") or [])
    if section in missing:
        missing.remove(section)

    state = {
        "jd_text": run.jd_text,
        "keyword_gaps": final.get("keywords_used", []),
        "sections_missing": missing,
    }
    retailored = await retailor_section(state, agent_service, section, sanitize_text(content))

    variants = final.get("variants") or {}
    for variant_key, section_text in retailored.items():
        bucket = dict(variants.get(variant_key, {}).get("sections", {}))
        bucket[section] = section_text
        variants[variant_key] = {
            **variants.get(variant_key, {}),
            "sections": bucket,
            "plain_text": _plain_text(bucket),
        }
    final["variants"] = variants

    overrides = {
        key: val.get("user_override")
        for key, val in (final.get("sections_editable") or {}).items()
        if val.get("user_override")
    }
    final = _rebuild_final_output(
        run,
        resume,
        agent_service,
        selected_variant=final.get("selected_variant", DEFAULT_VARIANT.value),
        variants={k: v.get("sections", {}) for k, v in variants.items()},
        overrides={k: str(v) for k, v in overrides.items() if v},
        missing=missing,
    )
    run.final_output = final
    if final.get("match_score", {}).get("current_overall") is not None:
        from decimal import Decimal

        run.ats_score_after = Decimal(str(final["match_score"]["current_overall"]))
    await session.commit()
    return final
