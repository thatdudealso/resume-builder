from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from packages.agent.schemas.variants import SECTION_KEYS

CanonicalSection = Literal["summary", "experience", "skills", "education"]


class SectionSuggestion(BaseModel):
    section: CanonicalSection
    reason: str = Field(min_length=1, max_length=500)
    priority: Literal["optional", "recommended"] = "optional"


class ResumeStructure(BaseModel):
    """Orchestrator understanding of a resume before section agents run."""

    header: str = ""
    sections: dict[str, str] = Field(default_factory=dict)
    section_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Canonical section -> original header label found in the resume",
    )
    sections_present: list[str] = Field(default_factory=list)
    sections_suggested: list[SectionSuggestion] = Field(default_factory=list)
    understanding_notes: str = ""

    def sections_with_content(self) -> list[str]:
        return [key for key in SECTION_KEYS if self.sections.get(key, "").strip()]

    def to_structured_dict(self) -> dict[str, str]:
        structured = {"header": self.header.strip()}
        for key in SECTION_KEYS:
            content = self.sections.get(key, "").strip()
            if content:
                structured[key] = content
        return structured
