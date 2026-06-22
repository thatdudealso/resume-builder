from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from packages.agent.nodes.format_output import format_output
from packages.agent.nodes.prepare_inputs import prepare_inputs
from packages.agent.sections.orchestrator import build_all_variants
from packages.agent.state import extract_keywords, score_coverage, split_sections


def test_split_sections():
    text = "SUMMARY\nLine one\nEXPERIENCE\nJob A"
    sections = split_sections(text)
    assert "summary" in sections or "experience" in sections


def test_split_sections_handles_objective_and_inline_experience_header():
    text = (
        "Ashish Gare\n"
        "ashish@example.com\n"
        "OBJECTIVE Driven technologist with Python experience.\n"
        "PROFESSIONAL Fraud Engineer November 2024 – Present\n"
        "EXPERIENCE Barclays - Whippany, NJ\n"
        "• Built fraud detection pipelines with Python.\n"
        "SKILLS Python, SQL, Airflow\n"
        "EDUCATION\n"
        "DePaul University - BS Computer Science"
    )
    sections = split_sections(text)
    assert sections.get("header", "").startswith("Ashish Gare")
    assert "Python" in sections.get("summary", "")
    assert "Barclays" in sections.get("experience", "")
    assert "Python" in sections.get("skills", "")
    assert "DePaul" in sections.get("education", "")


def test_prepare_inputs_does_not_set_section_drafts():
    text = (
        "Name Example\n"
        "OBJECTIVE Backend engineer.\n"
        "EXPERIENCE Acme Corp\n"
        "Built APIs.\n"
        "EDUCATION State University"
    )
    state = prepare_inputs(
        {
            "master_resume_text": text,
            "jd_text": "Looking for Python developer with API experience.",
        }
    )
    assert "section_drafts" not in state
    assert state.get("fatal_error") is None


@pytest.mark.asyncio
async def test_build_all_variants_tailors_present_sections_only():
    agent_service = AsyncMock()
    state = {
        "master_resume_structured": {
            "header": "Ashish Gare",
            "summary": "Driven technologist.",
            "experience": "Barclays - built pipelines.",
            "education": "DePaul University",
        },
        "section_drafts": {
            "summary": "Driven technologist.",
            "experience": "Barclays - built pipelines.",
            "education": "DePaul University",
        },
        "sections_to_tailor": ["summary", "experience", "education"],
        "user_added_sections": {},
        "keyword_gaps": [],
        "jd_text": "Python role",
        "selected_variant": "bold",
    }

    with patch(
        "packages.agent.sections.orchestrator.rewrite_section",
        new_callable=AsyncMock,
        return_value="Tailored",
    ) as rewrite:
        variants = await build_all_variants(state, agent_service)

    assert set(variants) == {"bold"}
    assert rewrite.await_count == 3
    assert "skills" not in variants["bold"]


def test_extract_keywords():
    keywords = extract_keywords("Python developer with FastAPI and PostgreSQL experience required")
    assert "python" in keywords or "fastapi" in keywords


def test_score_coverage():
    score, gaps = score_coverage("python fastapi", ["python", "java", "fastapi"])
    assert score == pytest.approx(66.67, rel=0.1)
    assert "java" in gaps


def test_prepare_inputs_success():
    state = prepare_inputs(
        {
            "master_resume_text": "A" * 60 + "\nEXPERIENCE\nBuilt APIs with Python.",
            "jd_text": "Looking for Python developer with API experience.",
        }
    )
    assert "jd_keywords" in state
    assert state.get("fatal_error") is None


def test_prepare_inputs_too_short():
    state = prepare_inputs({"master_resume_text": "short", "jd_text": "x" * 25})
    assert state.get("fatal_error")


def test_format_output_includes_header_and_suggestions():
    state = format_output(
        {
            "section_drafts": {"summary": "Engineer"},
            "master_resume_structured": {
                "header": "Jane Doe\njane@example.com",
                "summary": "Engineer",
            },
            "variants": {"balanced": {"summary": "Tailored engineer"}},
            "selected_variant": "balanced",
            "sections_suggested": [
                {"section": "skills", "reason": "Could help ATS", "priority": "optional"}
            ],
            "jd_keywords": [],
        }
    )
    final = state["final_output"]
    plain = final["plain_text"]
    assert plain.startswith("Jane Doe")
    assert final["sections_suggested"]


def test_format_output():
    state = format_output(
        {
            "section_drafts": {"summary": "Engineer"},
            "ats_score_before": 10.0,
            "ats_score_after": 50.0,
            "jd_keywords": ["python"],
        }
    )
    assert state["final_output"]["plain_text"]
    assert state["preview_text"]
