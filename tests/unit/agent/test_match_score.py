from __future__ import annotations

import pytest

from packages.agent.analysts.jd_analyst import fallback_jd_analysis
from packages.agent.analysts.resume_analyst import fallback_resume_analysis
from packages.agent.scoring.match_score import compute_match_score


def test_match_score_returns_weighted_overall():
    jd = fallback_jd_analysis("Senior Python API developer with PostgreSQL and 5 years experience required.")
    resume = fallback_resume_analysis(
        "SUMMARY\nEngineer\nEXPERIENCE\nBuilt Python APIs 2020-2022\nSKILLS\nPython, SQL",
        jd,
    )
    result = compute_match_score(jd, resume, "Built Python APIs")
    assert 0 <= result.overall <= 100
    assert len(result.components) == 5
    assert result.components[0].name == "must_have"


@pytest.mark.asyncio
async def test_agent_service_analyze_inputs():
    from packages.agent.service import AgentService

    service = AgentService("openai")
    analysis = await service.analyze_inputs(
        "Python developer with PostgreSQL required.",
        "SUMMARY\nEngineer\nEXPERIENCE\nBuilt APIs with Python\nSKILLS\nPython",
    )
    assert analysis["match_score_before"]["overall"] >= 0
    assert "jd_analysis" in analysis
    assert "resume_analysis" in analysis
