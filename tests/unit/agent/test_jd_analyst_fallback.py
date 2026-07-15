from __future__ import annotations

from packages.agent.analysts.jd_analyst import fallback_jd_analysis

_STOPWORD_TOKENS = {"between", "act", "technical", "customer"}


def test_fallback_jd_analysis_has_no_bare_stopword_requirements():
    analysis = fallback_jd_analysis(
        "Act as the technical bridge between engineering and customers."
    )
    requirement_terms = {req.requirement for req in analysis.must_have}
    assert requirement_terms.isdisjoint(_STOPWORD_TOKENS)
