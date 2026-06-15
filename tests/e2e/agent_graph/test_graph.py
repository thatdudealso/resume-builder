from __future__ import annotations

import pytest
from unittest.mock import patch

from packages.agent.graph import run_agent


@pytest.mark.asyncio
async def test_agent_graph_e2e():
    async def mock_llm(*, model: str, prompt: str, node: str) -> str:
        if node == "validate_output":
            return "no"
        return '{"summary": "Engineer", "experience": "Built APIs", "skills": "Python"}'

    initial = {
        "run_id": "r1",
        "user_id": "u1",
        "master_resume_text": "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python for 2020-2022.",
        "jd_text": "Seeking Python API developer with PostgreSQL skills required.",
        "retry_count": 0,
    }
    result = await run_agent(initial, mock_llm)
    assert result.get("final_output")
    assert result.get("validation_passed") is True
