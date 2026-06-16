from __future__ import annotations

from enum import StrEnum


class VariantName(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    BOLD = "bold"


DEFAULT_VARIANT = VariantName.BALANCED

VARIANT_ORDER: tuple[VariantName, ...] = (
    VariantName.CONSERVATIVE,
    VariantName.BALANCED,
    VariantName.BOLD,
)

VARIANT_INSTRUCTIONS: dict[VariantName, str] = {
    VariantName.CONSERVATIVE: (
        "Conservative: minimal changes — reorder bullets/skills and light rephrase only. "
        "Preserve original wording where possible."
    ),
    VariantName.BALANCED: (
        "Balanced: moderate tailoring — improve clarity, relevance, and JD keyword fit "
        "where the source resume supports it."
    ),
    VariantName.BOLD: (
        "Bold: maximum allowed tailoring — strongest action verbs and JD alignment "
        "without inventing any new facts."
    ),
}

SECTION_KEYS: tuple[str, ...] = ("summary", "experience", "skills", "education")
