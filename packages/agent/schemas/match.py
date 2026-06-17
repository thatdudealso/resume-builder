from __future__ import annotations

from pydantic import BaseModel, Field


class MatchComponentScore(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=100.0)
    weight: float
    detail: str = ""


class MatchScoreResult(BaseModel):
    overall: float = Field(ge=0.0, le=100.0)
    components: list[MatchComponentScore] = Field(default_factory=list)
    dealbreaker_flags: list[str] = Field(default_factory=list)
    evidence_coverage_pct: float = Field(ge=0.0, le=100.0, default=0.0)
