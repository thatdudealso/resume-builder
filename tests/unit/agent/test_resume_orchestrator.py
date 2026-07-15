from __future__ import annotations

import pytest

from packages.agent.nodes.understand_resume import understand_resume
from packages.agent.orchestrator.resume_orchestrator import understand_resume_structure
from packages.agent.providers._mock import mock_complete
from packages.agent.providers.base import AgentTask
from packages.agent.providers.openai_provider import OpenAIProvider
from packages.agent.schemas.variants import SECTION_KEYS
from packages.agent.service import AgentService
from packages.agent.state import split_sections

RESUME_SAMPLE = (
    "Ashish Gare\n"
    "ashish@example.com\n"
    "OBJECTIVE Driven technologist with Python experience.\n"
    "EXPERIENCE Barclays - Whippany, NJ\n"
    "• Built fraud detection pipelines with Python.\n"
    "EDUCATION DePaul University - BS Computer Science"
)


@pytest.mark.asyncio
async def test_understand_resume_structure_mock_provider():
    provider = OpenAIProvider()
    structure = await understand_resume_structure(RESUME_SAMPLE, provider)
    assert structure.header
    assert "summary" in structure.sections_present
    assert "experience" in structure.sections_present


@pytest.mark.asyncio
async def test_understand_resume_structure_fallback_without_llm():
    class UnconfiguredProvider(OpenAIProvider):
        def is_configured(self) -> bool:
            return False

    structure = await understand_resume_structure(RESUME_SAMPLE, UnconfiguredProvider())
    assert structure.sections.get("experience")
    assert "experience" in structure.sections_present


@pytest.mark.asyncio
async def test_understand_resume_node_updates_state():
    service = AgentService("openai")
    state = {
        "master_resume_text": RESUME_SAMPLE,
        "master_resume_structured": split_sections(RESUME_SAMPLE),
    }
    result = await understand_resume(state, service)
    assert result.get("sections_to_tailor")
    assert result.get("resume_structure")
    assert result.get("section_drafts")
    assert result.get("sections_missing") == []


@pytest.mark.asyncio
async def test_orchestrator_mock_json_shape():
    raw = mock_complete(AgentTask.RESUME_ORCHESTRATION, "", json_mode=True)
    assert "sections_present" in raw
    assert "sections_suggested" in raw


def test_resume_structure_only_outputs_present_sections():
    from packages.agent.schemas.resume_structure import ResumeStructure

    structure = ResumeStructure(
        header="Jane Doe",
        sections={"summary": "Engineer", "education": "State U"},
        sections_present=["summary", "education"],
    )
    structured = structure.to_structured_dict()
    assert "summary" in structured
    assert "education" in structured
    assert "experience" not in structured
    assert "skills" not in structured
    assert set(structured.keys()) <= {"header", *SECTION_KEYS}
