from __future__ import annotations

from packages.agent.nodes.format_output import format_output
from packages.agent.schemas.variants import (
    VARIANT_LABELS,
    VariantName,
    variant_option_labels,
)
from packages.agent.sections.orchestrator import pick_variant_sections


def test_format_output_includes_only_built_variants():
    state = {
        "variants": {"balanced": {"summary": "Tailored summary"}},
        "selected_variant": "balanced",
        "master_resume_structured": {
            "summary": "Original",
            "experience": "",
            "skills": "",
            "education": "",
        },
        "master_resume_text": "SUMMARY\nOriginal",
        "sections_missing": [],
        "jd_keywords": [],
    }
    result = format_output(state)
    final = result["final_output"]
    assert isinstance(final, dict)
    assert set(final["variants"]) == {"balanced"}


def test_format_output_applies_user_section_overrides():
    state = {
        "variants": {"balanced": {"summary": "Tailored summary"}},
        "selected_variant": "balanced",
        "user_section_overrides": {"summary": "User override"},
        "master_resume_structured": {
            "summary": "Original",
            "experience": "",
            "skills": "",
            "education": "",
        },
        "master_resume_text": "SUMMARY\nOriginal",
        "sections_missing": [],
        "jd_keywords": [],
    }
    result = format_output(state)
    final = result["final_output"]
    assert isinstance(final, dict)
    balanced = final["variants"]["balanced"]
    assert balanced["sections"]["summary"] == "User override"


def test_variant_option_labels_use_friendly_names():
    labels = variant_option_labels()
    assert labels["conservative"] == VARIANT_LABELS[VariantName.CONSERVATIVE]
    assert labels["balanced"] == "Standard fit"
    assert labels["bold"] == "Strong keyword match"


def test_variant_option_labels_cover_all_variants():
    assert set(variant_option_labels()) == {"conservative", "balanced", "bold"}


def test_pick_variant_sections_defaults_to_balanced():
    variants = {
        "conservative": {"summary": "A"},
        "balanced": {"summary": "B"},
        "bold": {"summary": "C"},
    }
    picked = pick_variant_sections(variants)
    assert picked["summary"] == "B"
