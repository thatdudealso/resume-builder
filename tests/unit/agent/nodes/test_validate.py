from __future__ import annotations

from packages.agent.nodes.validate_output import _rule_validate


def test_rule_validate_detects_extra_years():
    source = "Worked 2020-2022 at Company"
    draft = "Worked 2020-2024 at Company"
    errors = _rule_validate(source, draft)
    assert errors


def test_rule_validate_passes_same_years():
    source = "Worked 2020-2022 at Company"
    draft = "Worked 2020-2022 at Company"
    assert not _rule_validate(source, draft)
