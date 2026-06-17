from __future__ import annotations

from collections.abc import Awaitable, Callable

from packages.agent.service import AgentService
from packages.agent.state import AgentState

ProgressCallback = Callable[[dict], Awaitable[None]]


async def analyze_inputs(
    state: AgentState,
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
) -> AgentState:
    if state.get("fatal_error"):
        return state
    if on_progress:
        await on_progress({"event": "node_start", "node": "analyze_inputs"})
    analysis = await agent_service.analyze_inputs(
        state.get("jd_text", ""),
        state.get("master_resume_text", ""),
    )
    match_before = analysis.get("match_score_before") or {}
    if on_progress:
        await on_progress(
            {
                "event": "node_complete",
                "node": "analyze_inputs",
                "match_score_before": match_before.get("overall"),
            }
        )
    return {
        **state,
        **analysis,
        "ats_score_before": match_before.get("overall", state.get("ats_score_before", 0)),
    }
