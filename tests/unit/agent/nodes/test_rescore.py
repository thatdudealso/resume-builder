from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.agent.graph import _rescore_with_tailored_analysis


def _make_agent_service(overall: float) -> MagicMock:
    mock_score = MagicMock()
    mock_score.model_dump.return_value = {"overall": overall, "must_have": overall}
    svc = MagicMock()
    svc.analyze_resume = AsyncMock(return_value=MagicMock())
    svc.score_match = MagicMock(return_value=mock_score)
    return svc


def _base_state(plain: str = "Tailored resume text", variant: str = "balanced") -> dict:
    return {
        "final_output": {
            "plain_text": plain,
            "selected_variant": variant,
            "variants": {
                variant: {"sections": {}, "plain_text": plain, "match_score": {"overall": 61.0}},
            },
            "match_score": {
                "previous": {},
                "current": {"overall": 61.0},
                "previous_overall": None,
                "current_overall": 61.0,
            },
            "ats_score_after": 61.0,
        },
        "jd_analysis": {"keywords_weighted": [], "must_have": []},
        "ats_score_after": 61.0,
    }


@pytest.mark.asyncio
async def test_returns_state_unchanged_when_no_plain_text():
    state = _base_state(plain="")
    svc = MagicMock()
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result is state
    svc.analyze_resume.assert_not_called() if hasattr(svc, "analyze_resume") else None


@pytest.mark.asyncio
async def test_returns_state_unchanged_when_no_jd_analysis():
    state = _base_state()
    state["jd_analysis"] = None
    svc = MagicMock()
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result is state


@pytest.mark.asyncio
async def test_updates_top_level_ats_score_after():
    state = _base_state()
    svc = _make_agent_service(overall=78.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result["ats_score_after"] == 78.0


@pytest.mark.asyncio
async def test_updates_match_score_after_in_state():
    state = _base_state()
    svc = _make_agent_service(overall=78.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result["match_score_after"]["overall"] == 78.0


@pytest.mark.asyncio
async def test_updates_final_output_ats_score_after():
    state = _base_state()
    svc = _make_agent_service(overall=78.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result["final_output"]["ats_score_after"] == 78.0


@pytest.mark.asyncio
async def test_updates_final_output_match_score_current():
    state = _base_state()
    svc = _make_agent_service(overall=78.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    ms = result["final_output"]["match_score"]
    assert ms["current_overall"] == 78.0
    assert ms["current"]["overall"] == 78.0


@pytest.mark.asyncio
async def test_updates_selected_variant_match_score():
    state = _base_state(variant="bold")
    state["final_output"]["variants"]["balanced"] = {
        "sections": {}, "match_score": {"overall": 61.0}
    }
    svc = _make_agent_service(overall=82.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    assert result["final_output"]["variants"]["bold"]["match_score"]["overall"] == 82.0
    # Non-selected variant is untouched
    assert result["final_output"]["variants"]["balanced"]["match_score"]["overall"] == 61.0


@pytest.mark.asyncio
async def test_returns_original_state_on_llm_exception():
    state = _base_state()
    svc = MagicMock()
    svc.analyze_resume = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    result = await _rescore_with_tailored_analysis(state, svc)
    # Falls back to original state, not a new dict
    assert result is state
    assert result["ats_score_after"] == 61.0


@pytest.mark.asyncio
async def test_selected_variant_not_in_variants_no_keyerror():
    state = _base_state()
    state["final_output"]["selected_variant"] = "conservative"  # not in variants dict
    svc = _make_agent_service(overall=75.0)
    result = await _rescore_with_tailored_analysis(state, svc)
    # Top-level scores still updated
    assert result["ats_score_after"] == 75.0
    # variants dict unchanged (conservative wasn't in it)
    assert "conservative" not in result["final_output"]["variants"]
