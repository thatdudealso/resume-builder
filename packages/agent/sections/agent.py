from __future__ import annotations

from packages.agent.providers.base import AgentTask
from packages.agent.schemas.variants import VARIANT_INSTRUCTIONS, VariantName
from packages.agent.service import AgentService


def _requirements_block(
    missing: list[str],
    met: list[str],
    section: str,
) -> str:
    """Build the requirements context block for the rewrite prompt."""
    lines: list[str] = []

    if missing:
        lines.append(
            f"REQUIREMENTS TO ADDRESS in the {section.upper()} SECTION\n"
            "(currently missing or only partial in the source resume — address each one "
            "where the source provides honest supporting evidence; skip if no evidence exists):"
        )
        for item in missing[:10]:
            lines.append(f"  • {item}")
        lines.append("")

    if met:
        lines.append(
            "REQUIREMENTS ALREADY DEMONSTRATED — preserve this evidence in your rewrite:"
        )
        for item in met[:5]:
            lines.append(f"  • {item}")
        lines.append("")

    return "\n".join(lines)


async def _rewrite_skills(
    source_text: str,
    *,
    variant: VariantName,
    jd_text: str,
    met_requirements: list[str],
    priority_keywords: list[str],
    agent_service: AgentService,
) -> str:
    """Skills-specific rewrite/synthesis.

    Skills sections need different rules than experience: we may surface any skill
    confirmed by the requirements evidence even if it wasn't in a standalone skills
    section (it might be embedded in experience bullets). The 'never add anything not
    in source' rule that protects experience bullets would silently strip all
    JD-matching skills here.
    """
    confirmed = met_requirements[:15]
    keywords_str = ", ".join(priority_keywords[:20]) if priority_keywords else "none"

    if not source_text.strip() and not confirmed and not priority_keywords:
        return ""

    instruction = VARIANT_INSTRUCTIONS[variant]

    if source_text.strip():
        source_block = f"SOURCE SKILLS SECTION:\n{source_text[:3000]}\n\n"
        task = (
            "Rewrite this skills section to lead with skills most relevant to the job. "
            "You may include any skill confirmed in the requirements evidence below "
            "(evidence it is already in the candidate's background), even if it is not "
            "explicitly listed in the source skills section — it may be embedded in "
            "experience bullets. Do not invent skills with no evidence."
        )
    else:
        source_block = (
            "(No standalone skills section — skills are embedded in experience bullets.)\n\n"
        )
        task = (
            "Create a skills section from the confirmed requirements evidence below. "
            "Only list skills with a [met] or [partial] evidence entry — these are confirmed "
            "in the candidate's resume. Do not invent skills."
        )

    confirmed_block = (
        "\n".join(f"  • {r}" for r in confirmed)
        if confirmed
        else "  (none explicitly confirmed — infer from source if present)"
    )

    prompt = (
        f"You are an expert resume writer tailoring the SKILLS section for a job.\n\n"
        f"TAILORING STYLE: {variant.value} — {instruction}\n\n"
        f"TASK: {task}\n\n"
        "FORMAT RULES:\n"
        "- Lead with skills most relevant to this specific job\n"
        "- Use the JD's exact terminology for any skill the candidate has "
        "(e.g., if JD says 'TypeScript' and candidate used 'TypeScript', "
        "keep 'TypeScript' not 'JavaScript TS')\n"
        "- Clean format: comma-separated list or grouped by category\n"
        "- No section header, no markdown fences, no commentary\n\n"
        f"CONFIRMED SKILLS (evidence from candidate's resume):\n{confirmed_block}\n\n"
        f"PRIORITY JD SKILLS (lead with the most relevant): {keywords_str}\n\n"
        f"{source_block}"
        f"JOB DESCRIPTION (excerpt):\n{jd_text[:3000]}\n\n"
        "Return ONLY the skills section content."
    )
    response = await agent_service.complete(AgentTask.SECTION_REWRITE, prompt)
    return response.strip()[:3000]


async def rewrite_section(
    section: str,
    source_text: str,
    *,
    variant: VariantName,
    jd_text: str,
    keyword_gaps: list[str],
    missing_requirements: list[str] | None = None,
    met_requirements: list[str] | None = None,
    priority_keywords: list[str] | None = None,
    agent_service: AgentService,
) -> str:
    keywords_to_use = priority_keywords if priority_keywords else keyword_gaps

    if section == "skills":
        return await _rewrite_skills(
            source_text,
            variant=variant,
            jd_text=jd_text,
            met_requirements=met_requirements or [],
            priority_keywords=keywords_to_use,
            agent_service=agent_service,
        )

    if not source_text.strip():
        return ""

    instruction = VARIANT_INSTRUCTIONS[variant]
    keywords_str = ", ".join(keywords_to_use[:20]) if keywords_to_use else "none"

    req_block = _requirements_block(
        missing_requirements or [],
        met_requirements or [],
        section,
    )

    prompt = (
        f"You are an expert resume writer tailoring the {section.upper()} section "
        f"for a specific job application.\n\n"
        f"TAILORING STYLE: {variant.value} — {instruction}\n\n"
        "STRICT RULES (never violate these):\n"
        "- Never invent employers, dates, degrees, certifications, titles, or metrics\n"
        "- Every claim must be traceable to the source resume\n"
        "- Do not add skills, tools, or achievements that aren't in the source\n"
        "- Every strengthened bullet must cite a concrete activity from the source\n\n"
        "LANGUAGE ALIGNMENT (do this actively):\n"
        "- Mirror the job description's exact terminology and phrasing where honest\n"
        "- Use the same action verbs the JD uses (e.g., if JD says 'orchestrated', "
        "prefer that over 'managed' when describing the same activity)\n"
        "- Match the JD's tone: if the JD is quantitative, lead bullets with numbers; "
        "if leadership-focused, emphasise team/stakeholder impact\n"
        "- Use the JD's industry vocabulary and role-specific language throughout\n"
        "- Rephrase vague original wording into JD-aligned specifics where supported\n\n"
        f"{req_block}"
        f"Priority JD keywords by importance "
        f"(weave in where honest and natural): {keywords_str}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:6000]}\n\n"
        f"SOURCE {section.upper()} SECTION (do not invent beyond this):\n{source_text[:6000]}\n\n"
        f"Return ONLY the rewritten {section.upper()} section text. "
        "No section header, no markdown fences, no commentary."
    )
    response = await agent_service.complete(AgentTask.SECTION_REWRITE, prompt)
    return response.strip()[:8000]
