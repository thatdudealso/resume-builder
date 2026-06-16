from __future__ import annotations

import difflib

from packages.agent.schemas.variants import SECTION_KEYS, VARIANT_ORDER


def _change_type(original: str, updated: str) -> str:
    orig_lines = [line.strip() for line in original.splitlines() if line.strip()]
    new_lines = [line.strip() for line in updated.splitlines() if line.strip()]
    if orig_lines == new_lines:
        return "unchanged"
    if sorted(orig_lines) == sorted(new_lines) and orig_lines != new_lines:
        return "reorder"
    if len(updated) > len(original) * 1.05:
        return "expand"
    return "rephrase"


def build_changelog(
    original_sections: dict[str, str],
    variants: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for variant in VARIANT_ORDER:
        variant_key = variant.value
        proposed = variants.get(variant_key, {})
        for section in SECTION_KEYS:
            original = original_sections.get(section, "")
            updated = proposed.get(section, "")
            if not original and not updated:
                continue
            change = _change_type(original, updated)
            if change == "unchanged":
                continue
            ratio = difflib.SequenceMatcher(None, original, updated).ratio()
            entries.append(
                {
                    "section": section,
                    "variant": variant_key,
                    "type": change,
                    "detail": (
                        f"{section}: {change} "
                        f"({int(ratio * 100)}% similar to source)"
                    ),
                }
            )
    return entries


def build_sections_editable(
    original_sections: dict[str, str],
    variants: dict[str, dict[str, str]],
    user_overrides: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    overrides = user_overrides or {}
    editable: dict[str, dict[str, object]] = {}
    for section in SECTION_KEYS:
        original = original_sections.get(section, "")
        if not original and section not in variants.get("balanced", {}):
            if section not in (overrides.keys()):
                continue
        editable[section] = {
            "original": original,
            "proposed_by_variant": {
                variant.value: variants.get(variant.value, {}).get(section, "")
                for variant in VARIANT_ORDER
            },
            "user_override": overrides.get(section),
        }
    return editable
