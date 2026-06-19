from __future__ import annotations

from collections.abc import Awaitable, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from packages.agent.nodes.analyze_inputs import analyze_inputs
from packages.agent.nodes.format_output import format_output
from packages.agent.nodes.prepare_inputs import prepare_inputs
from packages.agent.nodes.rewrite_sections import rewrite_sections
from packages.agent.nodes.understand_resume import understand_resume
from packages.agent.nodes.validate_output import validate_output
from packages.agent.schemas.variants import DEFAULT_VARIANT
from packages.agent.service import AgentService
from packages.agent.state import AgentState

ProgressCallback = Callable[[dict], Awaitable[None]]


def _after_prepare(state: AgentState) -> str:
    if state.get("fatal_error"):
        return END
    return "understand_resume"


def _after_understand(state: AgentState) -> str:
    if state.get("fatal_error"):
        return END
    return "analyze_inputs"


def _after_analyze(state: AgentState) -> str:
    if state.get("fatal_error"):
        return END
    return "rewrite_sections"


def _after_validate(state: AgentState) -> str:
    if state.get("validation_passed"):
        return "format_output"
    if state.get("retry_count", 0) < 2:
        return "rewrite_sections"
    return "format_output"


def build_graph(
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(AgentState)

    async def prep_node(state: AgentState) -> AgentState:
        if on_progress:
            await on_progress({"event": "node_start", "node": "prepare_inputs"})
        result = prepare_inputs(state)
        if on_progress:
            await on_progress({"event": "node_complete", "node": "prepare_inputs"})
        return result

    async def understand_node(state: AgentState) -> AgentState:
        return await understand_resume(state, agent_service, on_progress)

    async def analyze_node(state: AgentState) -> AgentState:
        return await analyze_inputs(state, agent_service, on_progress)

    async def rewrite_node(state: AgentState) -> AgentState:
        if on_progress:
            await on_progress({"event": "node_start", "node": "rewrite_sections"})
        selected_variant = state.get("selected_variant") or DEFAULT_VARIANT.value
        seeded = {**state, "selected_variant": selected_variant}
        result = await rewrite_sections(seeded, agent_service)
        if on_progress:
            await on_progress({"event": "node_complete", "node": "rewrite_sections"})
        return result

    async def validate_node(state: AgentState) -> AgentState:
        if on_progress:
            await on_progress({"event": "node_start", "node": "validate_output"})
        result = await validate_output(state, agent_service)
        if on_progress:
            await on_progress({"event": "node_complete", "node": "validate_output"})
        return result

    async def format_node(state: AgentState) -> AgentState:
        if on_progress:
            await on_progress({"event": "node_start", "node": "format_output"})
        result = format_output(state, agent_service)
        if on_progress:
            await on_progress({"event": "node_complete", "node": "format_output"})
        return result

    graph.add_node("prepare_inputs", prep_node)
    graph.add_node("understand_resume", understand_node)
    graph.add_node("analyze_inputs", analyze_node)
    graph.add_node("rewrite_sections", rewrite_node)
    graph.add_node("validate_output", validate_node)
    graph.add_node("format_output", format_node)
    graph.set_entry_point("prepare_inputs")
    graph.add_conditional_edges(
        "prepare_inputs",
        _after_prepare,
        {"understand_resume": "understand_resume", END: END},
    )
    graph.add_conditional_edges(
        "understand_resume",
        _after_understand,
        {"analyze_inputs": "analyze_inputs", END: END},
    )
    graph.add_conditional_edges(
        "analyze_inputs",
        _after_analyze,
        {"rewrite_sections": "rewrite_sections", END: END},
    )
    graph.add_edge("rewrite_sections", "validate_output")
    graph.add_conditional_edges(
        "validate_output",
        _after_validate,
        {
            "format_output": "format_output",
            "rewrite_sections": "rewrite_sections",
        },
    )
    graph.add_edge("format_output", END)
    return graph.compile(checkpointer=checkpointer)


async def run_agent(
    initial: AgentState,
    agent_service: AgentService,
    on_progress: ProgressCallback | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> AgentState:
    """Run the resume tailoring graph using the selected LLM provider."""
    app = build_graph(agent_service, on_progress=on_progress, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": initial["run_id"]}} if checkpointer else {}
    result = await app.ainvoke(initial, config)
    return result
