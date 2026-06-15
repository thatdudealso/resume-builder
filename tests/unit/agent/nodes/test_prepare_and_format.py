from __future__ import annotations

import pytest

from packages.agent.nodes.format_output import format_output
from packages.agent.nodes.prepare_inputs import prepare_inputs
from packages.agent.state import extract_keywords, score_coverage, split_sections


def test_split_sections():
    text = "SUMMARY\nLine one\nEXPERIENCE\nJob A"
    sections = split_sections(text)
    assert "summary" in sections or "experience" in sections


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
