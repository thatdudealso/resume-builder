from __future__ import annotations

from packages.agent.providers.base import AgentTask
from packages.agent.schemas.variants import VARIANT_INSTRUCTIONS, VariantName
from packages.agent.service import AgentService


async def rewrite_section(
    section: str,
    source_text: str,
    *,
    variant: VariantName,
    jd_text: str,
    keyword_gaps: list[str],
    agent_service: AgentService,
) -> str:
    if not source_text.strip():
        return ""
    instruction = VARIANT_INSTRUCTIONS[variant]
    gaps_str = ", ".join(keyword_gaps[:15]) if keyword_gaps else "none"
    prompt = (
        f"You are an expert resume writer tailoring the {section.upper()} section "
        f"for a specific job application.\n\n"
        f"TAILORING STYLE: {variant.value} — {instruction}\n\n"
        "STRICT RULES (never violate these):\n"
        "- Never invent employers, dates, degrees, certifications, titles, or metrics\n"
        "- Every claim must be traceable to the source resume\n"
        "- Do not add skills, tools, or achievements that aren't in the source\n\n"
        "LANGUAGE ALIGNMENT (do this actively):\n"
        "- Mirror the job description's exact terminology and phrasing where honest\n"
        "- Use the same action verbs the JD uses (e.g., if JD says 'orchestrated', "
        "prefer that over 'managed' when describing the same activity)\n"
        "- Match the JD's tone: if the JD is quantitative, lead bullets with numbers; "
        "if leadership-focused, emphasise team/stakeholder impact\n"
        "- Use the JD's industry vocabulary and role-specific language throughout\n"
        "- Rephrase vague original wording into JD-aligned specifics where supported\n\n"
        f"Missing JD keywords to weave in naturally (only where honest): {gaps_str}\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:6000]}\n\n"
        f"SOURCE {section.upper()} SECTION (do not invent beyond this):\n{source_text[:6000]}\n\n"
        f"Return ONLY the rewritten {section.upper()} section text. "
        "No section header, no markdown fences, no commentary."
    )
    response = await agent_service.complete(AgentTask.SECTION_REWRITE, prompt)
    return response.strip()[:8000]
