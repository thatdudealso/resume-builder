from __future__ import annotations

import pytest

from packages.agent.analysts.fit_analyst import assess_fit
from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.providers import LLMProviderName


class _UnconfiguredProvider(LLMProvider):
    name = LLMProviderName.OPENAI

    def is_configured(self) -> bool:
        return False

    def model_for_task(self, task: AgentTask) -> str:
        return "test-model"

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        return "{}"


class _ConfiguredProvider(_UnconfiguredProvider):
    def __init__(self, response: str, *, fail: bool = False) -> None:
        self.response = response
        self.fail = fail

    def is_configured(self) -> bool:
        return True

    async def complete(self, task: AgentTask, prompt: str, *, json_mode: bool = False) -> str:
        if self.fail:
            raise RuntimeError("provider failed")
        assert task == AgentTask.FIT_ASSESSMENT
        assert json_mode is True
        assert "Python" in prompt
        return self.response


def _analyses() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    jd = {
        "must_have": [{"requirement": "Python"}],
        "nice_to_have": [{"requirement": "PostgreSQL"}],
        "seniority_level": "senior",
    }
    resume = {
        "seniority_inferred": "mid",
        "requirement_evidence": [
            {"requirement": "Python", "status": "met"},
            {"requirement": "AWS", "status": "missing"},
        ],
    }
    match = {
        "previous": {"overall": 42},
        "current": {
            "overall": 80,
            "components": [{"name": "must_have", "score": 75}],
            "dealbreaker_flags": [],
        },
    }
    return jd, resume, match


@pytest.mark.asyncio
async def test_assess_fit_uses_provider_json() -> None:
    jd, resume, match = _analyses()
    result = await assess_fit(
        jd,
        resume,
        match,
        _ConfiguredProvider(
            '{"verdict":"Strong fit","coaching_bullets":["Keep Python prominent"]}'
        ),
    )

    assert result.verdict == "Strong fit"
    assert result.coaching_bullets == ["Keep Python prominent"]


@pytest.mark.asyncio
async def test_assess_fit_fallback_handles_dealbreakers_and_missing_requirements() -> None:
    jd, resume, match = _analyses()
    current = match["current"]
    assert isinstance(current, dict)
    current["dealbreaker_flags"] = ["AWS"]

    result = await assess_fit(jd, resume, match, _UnconfiguredProvider())

    assert result.verdict == "Not a fit"
    assert any("AWS" in bullet for bullet in result.coaching_bullets)


@pytest.mark.asyncio
async def test_assess_fit_falls_back_when_provider_fails() -> None:
    jd, resume, match = _analyses()
    result = await assess_fit(jd, resume, match, _ConfiguredProvider("{}", fail=True))

    assert result.verdict == "Strong fit"


@pytest.mark.asyncio
async def test_assess_fit_fallback_moderate_without_specific_bullets() -> None:
    result = await assess_fit(
        {},
        {"requirement_evidence": []},
        {"current": {"overall": 50}},
        _UnconfiguredProvider(),
    )

    assert result.verdict == "Moderate fit"
    assert result.coaching_bullets == [
        "Resume covers the core requirements — review keyword alignment for ATS."
    ]


@pytest.mark.asyncio
async def test_assess_fit_fallback_defaults_non_numeric_scores() -> None:
    result = await assess_fit(
        {},
        {"requirement_evidence": []},
        {"current": {"overall": object()}},
        _UnconfiguredProvider(),
    )

    assert result.verdict == "Not a fit"
