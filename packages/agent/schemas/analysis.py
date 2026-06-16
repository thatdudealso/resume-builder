from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WeightedKeyword(BaseModel):
    term: str
    weight: float = Field(ge=0.0, le=1.0)


class JDRequirement(BaseModel):
    requirement: str
    category: Literal["skill", "cert", "education", "years", "other"] = "other"


class JDAnalysis(BaseModel):
    must_have: list[JDRequirement] = Field(default_factory=list)
    nice_to_have: list[JDRequirement] = Field(default_factory=list)
    role_type: Literal["ic", "manager", "hybrid", "unknown"] = "unknown"
    seniority_level: Literal["junior", "mid", "senior", "lead", "executive", "unknown"] = "unknown"
    responsibilities: list[str] = Field(default_factory=list)
    dealbreakers: list[str] = Field(default_factory=list)
    keywords_weighted: list[WeightedKeyword] = Field(default_factory=list)


class ResumeRole(BaseModel):
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)


class RequirementEvidence(BaseModel):
    requirement: str
    status: Literal["met", "partial", "missing"] = "missing"
    evidence_quote: str = ""


class ResumeAnalysis(BaseModel):
    sections_present: dict[str, bool] = Field(
        default_factory=lambda: {
            "summary": False,
            "experience": False,
            "skills": False,
            "education": False,
        }
    )
    sections_missing: list[str] = Field(default_factory=list)
    seniority_inferred: Literal["junior", "mid", "senior", "lead", "executive", "unknown"] = "unknown"
    roles: list[ResumeRole] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    requirement_evidence: list[RequirementEvidence] = Field(default_factory=list)
