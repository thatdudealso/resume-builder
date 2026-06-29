from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_current_user, get_db
from packages.agent.analysts.input_analyst import analyze_inputs_combined
from packages.agent.providers.registry import get_provider, resolve_provider_name
from packages.agent.schemas.providers import DEFAULT_PROVIDER
from packages.agent.scoring.match_score import compute_match_score
from packages.db.models.resume import MasterResume
from packages.db.models.user import User

router = APIRouter(prefix="/score", tags=["score"])


class ScorePreviewRequest(BaseModel):
    resume_id: UUID
    jd_text: str = Field(min_length=20, max_length=50000)
    provider: str = Field(default=DEFAULT_PROVIDER.value)


@router.post("/preview")
async def score_preview(
    body: ScorePreviewRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    resume = await session.get(MasterResume, body.resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status_code=404, detail="Resume not found")

    provider_name = resolve_provider_name(body.provider)
    provider = get_provider(provider_name)

    try:
        jd_analysis, resume_analysis = await analyze_inputs_combined(
            body.jd_text,
            resume.raw_text,
            provider,
        )
        score = compute_match_score(jd_analysis, resume_analysis, resume.raw_text)
        return {
            "score": score.model_dump(),
            "overall": score.overall,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Score preview failed: {exc}") from exc
