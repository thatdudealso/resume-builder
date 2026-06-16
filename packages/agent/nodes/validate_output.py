from __future__ import annotations

import re

from packages.agent.providers.base import AgentTask
from packages.agent.schemas.variants import DEFAULT_VARIANT
from packages.agent.service import AgentService
from packages.agent.state import AgentState


def _rule_validate(source: str, draft: str) -> list[str]:
    errors: list[str] = []
    year_pattern = re.compile(r"\b((?:19|20)\d{2})\b")
    source_years = set(year_pattern.findall(source))
    draft_years = set(year_pattern.findall(draft))
    extra_years = draft_years - source_years
    if extra_years:
        errors.append(f"Draft introduces years not in source: {sorted(extra_years)}")
    return errors


async def validate_output(state: AgentState, agent_service: AgentService) -> AgentState:
    source = state.get("master_resume_text", "")
    selected = state.get("selected_variant") or DEFAULT_VARIANT.value
    variants = state.get("variants") or {}
    drafts = variants.get(selected) or state.get("section_drafts", {})
    draft = "\n".join(drafts.values())
    errors = _rule_validate(source, draft)
    if not errors:
        prompt = (
            "Does the draft introduce employers, degrees, or metrics"
            " not supported by the source resume?"
            " Answer ONLY yes or no.\n"
            f"Source:\n{source[:4000]}\nDraft:\n{draft[:4000]}"
        )
        answer = await agent_service.complete(AgentTask.VALIDATION, prompt)
        if answer.strip().lower().startswith("y"):
            errors.append("LLM detected unsupported claims")
    passed = len(errors) == 0
    retry = state.get("retry_count", 0)
    if not passed and retry < 2:
        retry += 1
    return {
        **state,
        "section_drafts": drafts,
        "validation_errors": errors,
        "validation_passed": passed,
        "retry_count": retry,
    }
