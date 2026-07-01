from __future__ import annotations

from collections.abc import Awaitable, Callable

from packages.agent.service import AgentService
from packages.agent.state import AgentState

ProgressCallback = Callable[[dict], Awaitable[None]]


async def assess_fit(
    state: AgentState,
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
) -> AgentState:
    if state.get("fatal_error"):
        return state
    if on_progress:
        await on_progress({"event": "node_start", "node": "assess_fit"})

    final_output = dict(state.get("final_output") or {})

    match_score = final_output.get("match_score")
    if not match_score:
        # format_output stores a flat dict in state["match_score_after"];
        # fit_analyst expects {"current": {...}, "previous": {...}}
        flat = state.get("match_score_after") or {}
        match_score = {"current": flat, "previous": state.get("match_score_before") or {}}

    fit = await agent_service.assess_fit(
        final_output.get("jd_analysis") or state.get("jd_analysis") or {},
        final_output.get("resume_analysis") or state.get("resume_analysis") or {},
        match_score,
    )
    final_output["fit_assessment"] = fit

    if on_progress:
        await on_progress(
            {"event": "node_complete", "node": "assess_fit", "verdict": fit.get("verdict")}
        )
    return {**state, "final_output": final_output}
