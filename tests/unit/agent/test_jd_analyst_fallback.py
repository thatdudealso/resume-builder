from __future__ import annotations

from packages.agent.analysts.jd_analyst import fallback_jd_analysis

_STOPWORD_TOKENS = {"between", "across", "within", "customer", "technical", "using"}


def test_fallback_jd_analysis_has_no_bare_stopword_requirements():
    analysis = fallback_jd_analysis(
        "Working across teams within the customer domain using technical "
        "judgement between projects."
    )
    requirement_terms = {req.requirement for req in analysis.must_have}
    requirement_terms |= {req.requirement for req in analysis.nice_to_have}
    assert requirement_terms.isdisjoint(_STOPWORD_TOKENS)


def test_fallback_jd_analysis_keeps_short_skills():
    analysis = fallback_jd_analysis("Requires sql aws git and strong fundamentals.")
    requirement_terms = {req.requirement for req in analysis.must_have}
    requirement_terms |= {req.requirement for req in analysis.nice_to_have}
    assert {"sql", "aws", "git"} <= requirement_terms
