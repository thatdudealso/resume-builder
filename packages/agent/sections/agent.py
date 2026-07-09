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
    if not source_text.strip():
        return ""

    instruction = VARIANT_INSTRUCTIONS[variant]

    # Use LLM-weighted keywords when available; fall back to naive regex gaps
    keywords_to_use = priority_keywords if priority_keywords else keyword_gaps
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
