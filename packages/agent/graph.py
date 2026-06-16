from __future__ import annotations

from collections.abc import Awaitable, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from packages.agent.nodes.format_output import format_output
from packages.agent.nodes.prepare_inputs import prepare_inputs
from packages.agent.nodes.rewrite_sections import rewrite_sections
from packages.agent.nodes.validate_output import validate_output
from packages.agent.state import AgentState

LLMComplete = Callable[..., Awaitable[str]]


def _after_prepare(state: AgentState) -> str:
    if state.get("fatal_error"):
        return END
    return "rewrite_sections"


def _after_validate(state: AgentState) -> str:
    if state.get("validation_passed"):
        return "format_output"
    if state.get("retry_count", 0) < 2:
        return "rewrite_sections"
    return END


def build_graph(
    llm_complete: LLMComplete,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(AgentState)

    async def prep_node(state: AgentState) -> AgentState:
        return prepare_inputs(state)

    async def rewrite_node(state: AgentState) -> AgentState:
        return await rewrite_sections(state, llm_complete)

    async def validate_node(state: AgentState) -> AgentState:
        return await validate_output(state, llm_complete)

    async def format_node(state: AgentState) -> AgentState:
        return format_output(state)

    graph.add_node("prepare_inputs", prep_node)
    graph.add_node("rewrite_sections", rewrite_node)
    graph.add_node("validate_output", validate_node)
    graph.add_node("format_output", format_node)
    graph.set_entry_point("prepare_inputs")
    graph.add_conditional_edges(
        "prepare_inputs",
        _after_prepare,
        {"rewrite_sections": "rewrite_sections", END: END},
    )
    graph.add_edge("rewrite_sections", "validate_output")
    graph.add_conditional_edges(
        "validate_output",
        _after_validate,
        {"format_output": "format_output", "rewrite_sections": "rewrite_sections", END: END},
    )
    graph.add_edge("format_output", END)
    return graph.compile(checkpointer=checkpointer)


async def run_agent(
    initial: AgentState,
    llm_complete: LLMComplete,
    checkpointer: BaseCheckpointSaver | None = None,
) -> AgentState:
    """Run the resume tailoring graph.

    When a checkpointer is provided, the run is keyed by ``initial["run_id"]``
    so the graph can resume from the last saved checkpoint if the container
    restarts mid-run.
    """
    app = build_graph(llm_complete, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": initial["run_id"]}} if checkpointer else {}
    result = await app.ainvoke(initial, config)
    return result
