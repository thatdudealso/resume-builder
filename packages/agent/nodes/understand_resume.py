from __future__ import annotations

from collections.abc import Awaitable, Callable

from packages.agent.orchestrator.resume_orchestrator import understand_resume_structure
from packages.agent.schemas.variants import SECTION_KEYS
from packages.agent.service import AgentService
from packages.agent.state import AgentState

ProgressCallback = Callable[[dict], Awaitable[None]]


async def understand_resume(
    state: AgentState,
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
) -> AgentState:
    if state.get("fatal_error"):
        return state
    if on_progress:
        await on_progress({"event": "node_start", "node": "understand_resume"})

    structure = await understand_resume_structure(
        state.get("master_resume_text", ""),
        agent_service.provider,
        parser_hint=state.get("master_resume_structured"),
    )
    structured = structure.to_structured_dict()
    section_drafts = {key: structure.sections.get(key, "") for key in SECTION_KEYS}

    if on_progress:
        await on_progress(
            {
                "event": "node_complete",
                "node": "understand_resume",
                "sections_present": structure.sections_present,
                "sections_suggested": [s.section for s in structure.sections_suggested],
            }
        )

    return {
        **state,
        "resume_structure": structure.model_dump(),
        "master_resume_structured": structured,
        "section_drafts": section_drafts,
        "sections_to_tailor": structure.sections_present,
        "sections_suggested": [s.model_dump() for s in structure.sections_suggested],
        "sections_missing": [],
    }
