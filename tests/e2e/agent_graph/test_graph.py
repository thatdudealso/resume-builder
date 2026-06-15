from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver

from packages.agent.graph import run_agent, build_graph


_INITIAL = {
    "run_id": "r1",
    "user_id": "u1",
    "master_resume_text": "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python for 2020-2022.",
    "jd_text": "Seeking Python API developer with PostgreSQL skills required.",
    "retry_count": 0,
}


async def _mock_llm(*, model: str, prompt: str, node: str) -> str:
    if node == "validate_output":
        return "no"
    return '{"summary": "Engineer", "experience": "Built APIs", "skills": "Python"}'


@pytest.mark.asyncio
async def test_agent_graph_e2e():
    result = await run_agent(_INITIAL, _mock_llm)
    assert result.get("final_output")
    assert result.get("validation_passed") is True


@pytest.mark.asyncio
async def test_agent_graph_with_checkpointer_completes():
    """Graph compiles and runs correctly when a checkpointer is wired in."""
    checkpointer = MemorySaver()
    result = await run_agent(_INITIAL, _mock_llm, checkpointer=checkpointer)
    assert result.get("final_output")
    assert result.get("validation_passed") is True


@pytest.mark.asyncio
async def test_agent_graph_checkpoint_state_readable_after_completion():
    """After a completed run, the final state is readable via aget_state.

    This is the key production behaviour: if a container restarts between the
    run completing and the DB write, we can recover the result from the
    checkpoint rather than re-running the expensive LLM nodes.
    """
    checkpointer = MemorySaver()
    result = await run_agent(_INITIAL, _mock_llm, checkpointer=checkpointer)
    assert result.get("final_output")

    # The compiled graph exposes aget_state keyed by thread_id
    app = build_graph(_mock_llm, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": _INITIAL["run_id"]}}
    saved = await app.aget_state(config)
    assert saved.values.get("final_output") == result.get("final_output")
