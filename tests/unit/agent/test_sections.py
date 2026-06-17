from __future__ import annotations

from packages.agent.sections.orchestrator import pick_variant_sections


def test_pick_variant_sections_defaults_to_balanced():
    variants = {
        "conservative": {"summary": "A"},
        "balanced": {"summary": "B"},
        "bold": {"summary": "C"},
    }
    picked = pick_variant_sections(variants)
    assert picked["summary"] == "B"
