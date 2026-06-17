from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from apps.web.config import settings
from apps.web.dependencies import get_current_user, get_db
from apps.web.services.run_executor import execute_run, get_run_queue
from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.core.security.sanitization import sanitize_text
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume
from packages.db.models.user import User

router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    resume_id: UUID
    jd_text: str = Field(min_length=20, max_length=50000)


def _serialize_run(run: AgentRun, can_view: bool) -> dict:
    payload = {
        "run_id": str(run.id),
        "status": run.status,
        "output_locked": run.output_locked,
        "is_free_trial_run": run.is_free_trial_run,
        "ats_score_before": float(run.ats_score_before) if run.ats_score_before else None,
        "ats_score_after": float(run.ats_score_after) if run.ats_score_after else None,
        "preview_text": run.preview_text,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
    if can_view and run.final_output:
        payload["final_output"] = run.final_output
    elif run.output_locked:
        payload["final_output"] = None
    return payload


@router.post("")
async def create_run(
    body: CreateRunRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    resume = await session.get(MasterResume, body.resume_id)
    if resume is None or resume.user_id != user.id:
        raise HTTPException(status_code=404, detail="Resume not found")
    access = AccessService(session)
    decision = await access.can_start_run(user.id)
    if decision.mode == RunAccessMode.BLOCKED:
        raise HTTPException(status_code=403, detail=decision.message)
    jd = sanitize_text(body.jd_text)
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text=jd,
        output_locked=decision.mode == RunAccessMode.LOCKED,
        is_free_trial_run=decision.mode == RunAccessMode.FREE,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    asyncio.create_task(_run_background(run.id))
    return {"run_id": str(run.id), "status": run.status, "output_locked": run.output_locked}


async def _run_background(run_id: UUID) -> None:
    from packages.db.session import SessionLocal

    async with SessionLocal() as session:
        await execute_run(session, run_id)


@router.get("/{run_id}")
async def get_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    access = AccessService(session)
    can_view = await access.can_view_output(user.id, run)
    if run.output_locked and not can_view:
        return _serialize_run(run, False)
    return _serialize_run(run, can_view)


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    access = AccessService(session)
    can_view = await access.can_view_output(user.id, run)
    queue = get_run_queue(str(run_id))

    async def event_generator():
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=120.0)
            except TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                break
            if item.get("event") == "done":
                payload = {"locked": item.get("locked", False)}
                if can_view or not payload["locked"]:
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                else:
                    yield f"event: done\ndata: {json.dumps({'locked': True, 'redacted': True})}\n\n"
                break
            if item.get("event") == "error":
                yield f"event: error\ndata: {json.dumps(item)}\n\n"
                break
            yield f"event: progress\ndata: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{run_id}/unlock")
async def unlock_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output_locked:
        return {"already_unlocked": True}
    return {
        "run_id": str(run_id),
        "stripe_checkout": "/api/v1/billing/stripe/checkout",
        "crypto_invoice": "/api/v1/billing/crypto/invoice",
        "price_usd": settings.run_unlock_price_usd,
    }
