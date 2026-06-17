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
    prompt = (
        f"You are the {section.upper()} section agent for resume tailoring.\n"
        f"Variant: {variant.value}. {instruction}\n"
        "STRICT RULES: never invent employers, dates, degrees, certifications, or metrics. "
        "Reordering and light inference are allowed only when supported by the source text.\n"
        f"Missing JD keywords to address only when honestly supported: "
        f"{', '.join(keyword_gaps[:15])}\n"
        f"Job description:\n{jd_text[:6000]}\n"
        f"Source {section} section:\n{source_text[:6000]}\n"
        f"Return only the rewritten {section} section text. No markdown fences."
    )
    response = await agent_service.complete(AgentTask.SECTION_REWRITE, prompt)
    return response.strip()[:8000]
