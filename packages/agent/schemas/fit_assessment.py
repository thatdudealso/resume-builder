from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FitAssessment(BaseModel):
    verdict: Literal["Strong fit", "Moderate fit", "Not a fit"] = "Moderate fit"
    coaching_bullets: list[str] = Field(default_factory=list)
