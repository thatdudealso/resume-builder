from __future__ import annotations

import pytest

from packages.agent.schemas.analysis import JDAnalysis, JDRequirement


def test_llm_shaped_payload_normalizes_technical_skill_to_skill():
    analysis = JDAnalysis.model_validate(
        {
            "must_have": [{"requirement": "Python", "category": "technical skill"}],
        }
    )
    assert analysis.must_have[0].requirement == "Python"
    assert analysis.must_have[0].category == "skill"


@pytest.mark.parametrize(
    ("raw_category", "expected"),
    [
        ("responsibility", "other"),
        ("certification", "cert"),
        ("degree", "education"),
        ("education", "education"),
        ("5 years", "years"),
        ("years", "years"),
        ("soft skill", "skill"),
        ("skill", "skill"),
        ("cert", "cert"),
        ("other", "other"),
    ],
)
def test_category_normalizes_free_form_values(raw_category: str, expected: str) -> None:
    req = JDRequirement.model_validate({"requirement": "X", "category": raw_category})
    assert req.category == expected


def test_canonical_category_values_pass_through_unchanged():
    for canonical in ("skill", "cert", "education", "years", "other"):
        req = JDRequirement.model_validate({"requirement": "X", "category": canonical})
        assert req.category == canonical
