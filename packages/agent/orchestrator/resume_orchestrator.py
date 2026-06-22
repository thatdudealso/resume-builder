from __future__ import annotations

import logging

from packages.agent.providers.base import AgentTask, LLMProvider
from packages.agent.schemas.resume_structure import ResumeStructure, SectionSuggestion
from packages.agent.schemas.variants import SECTION_KEYS
from packages.agent.state import split_sections
from packages.agent.utils.json_parse import parse_json_response

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT = """You are the resume orchestrator. Read the entire resume and map its content
into canonical sections for downstream tailoring agents.

Canonical sections (only these four):
- summary: objective, profile, about, professional summary, or opening narrative
- experience: work history, employment, roles, projects presented as jobs
- skills: dedicated skills/competencies/technologies section (NOT bullet lists inside jobs)
- education: degrees, certifications listed as education

Rules:
1. Read content, not just header names. "OBJECTIVE", "PROFILE", "ABOUT ME" -> summary.
2. "PROFESSIONAL EXPERIENCE", "WORK HISTORY", inline job blocks -> experience.
3. Put name, phone, email, location in header — never in summary.
4. If skills appear only inside job bullets, leave skills empty (do not duplicate experience).
5. Never invent content. Extract only what exists in the source resume.
6. sections_present = canonical keys with real content in the resume.
7. sections_suggested = optional sections absent from the resume that could help (never required).
   Use priority "recommended" only when the job context strongly benefits; otherwise "optional".
8. section_sources maps each present canonical key to the original header/label you inferred.

Return JSON only with keys:
header (string),
sections (object with optional summary/experience/skills/education string values),
section_sources (object mapping canonical key -> original label),
sections_present (list of canonical keys with content),
sections_suggested (list of {{section, reason, priority}} for absent sections only),
understanding_notes (brief string explaining non-obvious mapping decisions).

Parser hint (may be incomplete — trust the full resume text):
{parser_hint}

Resume:
{resume_text}
"""


def _fallback_structure(resume_text: str) -> ResumeStructure:
    parsed = split_sections(resume_text)
    header = parsed.get("header", "").strip()
    sections = {key: parsed.get(key, "").strip() for key in SECTION_KEYS}
    present = [key for key in SECTION_KEYS if sections.get(key)]
    sources = {
        key: "parser"
        for key in present
    }
    suggested: list[SectionSuggestion] = []
    if not sections.get("skills") and sections.get("experience"):
        suggested.append(
            SectionSuggestion(
                section="skills",
                reason="No dedicated skills section found; skills may be embedded in experience.",
                priority="optional",
            )
        )
    return ResumeStructure(
        header=header,
        sections=sections,
        section_sources=sources,
        sections_present=present,
        sections_suggested=suggested,
        understanding_notes="Fallback parser mapping (LLM orchestrator unavailable).",
    )


def _normalize_structure(data: dict[str, object], resume_text: str) -> ResumeStructure:
    structure = ResumeStructure.model_validate(data)
    sections: dict[str, str] = {}
    sources: dict[str, str] = dict(structure.section_sources)

    for key in SECTION_KEYS:
        content = structure.sections.get(key, "").strip()
        if content:
            sections[key] = content
            sources.setdefault(key, sources.get(key, "orchestrator"))

    present = [key for key in SECTION_KEYS if sections.get(key)]
    suggested = [
        item
        for item in structure.sections_suggested
        if item.section not in present
    ]

    header = structure.header.strip()
    if not header:
        fallback = split_sections(resume_text)
        header = fallback.get("header", "").strip()

    return ResumeStructure(
        header=header,
        sections=sections,
        section_sources=sources,
        sections_present=present,
        sections_suggested=suggested,
        understanding_notes=structure.understanding_notes.strip(),
    )


async def understand_resume_structure(
    resume_text: str,
    provider: LLMProvider,
    *,
    parser_hint: dict[str, str] | None = None,
) -> ResumeStructure:
    hint = parser_hint or split_sections(resume_text)
    hint_summary = {k: (v[:120] + "…" if len(v) > 120 else v) for k, v in hint.items() if v.strip()}

    if provider.is_configured():
        try:
            prompt = ORCHESTRATOR_PROMPT.format(
                parser_hint=hint_summary,
                resume_text=resume_text[:14000],
            )
            raw = await provider.complete(AgentTask.RESUME_ORCHESTRATION, prompt, json_mode=True)
            data = parse_json_response(raw)
            structure = _normalize_structure(data, resume_text)
            logger.info(
                "Resume orchestrator mapped sections=%s suggested=%s",
                structure.sections_present,
                [s.section for s in structure.sections_suggested],
            )
            return structure
        except Exception:
            logger.exception("Resume orchestrator LLM failed; using parser fallback")

    return _fallback_structure(resume_text)
