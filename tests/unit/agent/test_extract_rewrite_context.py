from __future__ import annotations

from packages.agent.sections.orchestrator import _extract_rewrite_context


def test_empty_state_returns_empty_lists():
    missing, met, kws = _extract_rewrite_context({})
    assert missing == []
    assert met == []
    assert kws == []


def test_missing_status_goes_into_missing_reqs():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {"requirement": "5 years Python", "status": "missing", "evidence_quote": ""},
            ]
        }
    }
    missing, met, _ = _extract_rewrite_context(state)
    assert len(missing) == 1
    assert "[missing]" in missing[0]
    assert "5 years Python" in missing[0]
    assert met == []


def test_partial_with_quote_includes_hint():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {
                    "requirement": "Team lead experience",
                    "status": "partial",
                    "evidence_quote": "Led a small group of contractors",
                },
            ]
        }
    }
    missing, _, _ = _extract_rewrite_context(state)
    assert len(missing) == 1
    assert "[partial]" in missing[0]
    assert "Led a small group" in missing[0]


def test_partial_without_quote_omits_hint():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {"requirement": "Team lead experience", "status": "partial", "evidence_quote": ""},
            ]
        }
    }
    missing, _, _ = _extract_rewrite_context(state)
    assert len(missing) == 1
    assert "[partial]" in missing[0]
    assert "(found:" not in missing[0]


def test_met_with_quote_goes_into_met_reqs():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {
                    "requirement": "SQL proficiency",
                    "status": "met",
                    "evidence_quote": "Wrote complex SQL queries",
                },
            ]
        }
    }
    missing, met, _ = _extract_rewrite_context(state)
    assert missing == []
    assert len(met) == 1
    assert "[met]" in met[0]
    assert "SQL proficiency" in met[0]


def test_met_without_quote_excluded_from_met_reqs():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {"requirement": "SQL proficiency", "status": "met", "evidence_quote": ""},
            ]
        }
    }
    _, met, _ = _extract_rewrite_context(state)
    assert met == []


def test_non_dict_items_in_evidence_are_filtered():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                "not a dict",
                None,
                42,
                {"requirement": "Python", "status": "missing", "evidence_quote": ""},
            ]
        }
    }
    missing, _, _ = _extract_rewrite_context(state)
    assert len(missing) == 1
    assert "Python" in missing[0]


def test_priority_keywords_sorted_by_weight_descending():
    state = {
        "jd_analysis": {
            "keywords_weighted": [
                {"term": "SQL", "weight": 0.5},
                {"term": "Python", "weight": 0.9},
                {"term": "Docker", "weight": 0.3},
            ]
        }
    }
    _, _, kws = _extract_rewrite_context(state)
    assert kws == ["Python", "SQL", "Docker"]


def test_keywords_missing_term_field_are_skipped():
    state = {
        "jd_analysis": {
            "keywords_weighted": [
                {"term": "Python", "weight": 0.9},
                {"term": None, "weight": 0.8},
                {"weight": 0.7},
            ]
        }
    }
    _, _, kws = _extract_rewrite_context(state)
    assert kws == ["Python"]


def test_mixed_statuses_correctly_partitioned():
    state = {
        "resume_analysis": {
            "requirement_evidence": [
                {"requirement": "Python", "status": "met", "evidence_quote": "Built with Python"},
                {"requirement": "Docker", "status": "missing", "evidence_quote": ""},
                {"requirement": "AWS", "status": "partial", "evidence_quote": "Used EC2"},
            ]
        }
    }
    missing, met, _ = _extract_rewrite_context(state)
    assert len(missing) == 2  # missing + partial
    assert len(met) == 1
    assert any("Docker" in m for m in missing)
    assert any("AWS" in m for m in missing)
    assert any("Python" in m for m in met)
