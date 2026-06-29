from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import StreamingResponse

from apps.web.config import settings
from apps.web.dependencies import get_current_user, get_db
from apps.web.services.run_editor import (
    add_section_and_retailor,
    generate_variant,
    select_variant,
    update_section_override,
)
from apps.web.services.run_executor import get_run_queue
from apps.web.services.run_launcher import RunLaunchError, create_and_schedule_run
from packages.agent.providers.registry import list_provider_options
from packages.agent.schemas.providers import DEFAULT_PROVIDER
from packages.agent.schemas.variants import DEFAULT_VARIANT, SECTION_KEYS
from packages.core.access.service import AccessService
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume
from packages.db.models.user import User

router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    resume_id: UUID
    jd_text: str = Field(min_length=20, max_length=50000)
    llm_provider: str = Field(default=DEFAULT_PROVIDER.value)
    variant: str = Field(default=DEFAULT_VARIANT.value)


class SelectVariantRequest(BaseModel):
    variant: str


class SectionEditRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class AddSectionRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    retailor: bool = True


def _serialize_run(run: AgentRun, can_view: bool) -> dict:
    payload = {
        "run_id": str(run.id),
        "status": run.status,
        "llm_provider": run.llm_provider,
        "output_locked": run.output_locked,
        "is_free_trial_run": run.is_free_trial_run,
        "master_resume_id": str(run.master_resume_id),
        "jd_text": run.jd_text,
        "ats_score_before": float(run.ats_score_before) if run.ats_score_before else None,
        "ats_score_after": float(run.ats_score_after) if run.ats_score_after else None,
        "match_score": {
            "previous": float(run.ats_score_before) if run.ats_score_before else None,
            "current": float(run.ats_score_after) if run.ats_score_after else None,
        },
        "preview_text": run.preview_text,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
    resume = getattr(run, "resume", None)
    if resume is not None:
        payload["resume_filename"] = resume.filename
    if can_view and run.final_output:
        payload["final_output"] = run.final_output
    elif run.output_locked:
        payload["final_output"] = None
    return payload


@router.get("/providers")
async def list_llm_providers() -> dict:
    return {"providers": list_provider_options()}


@router.post("")
async def create_run(
    body: CreateRunRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        return await create_and_schedule_run(
            session,
            user,
            resume_id=body.resume_id,
            jd_text=body.jd_text,
            llm_provider=body.llm_provider,
            variant=body.variant,
        )
    except RunLaunchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{run_id}")
async def get_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(
        AgentRun,
        run_id,
        options=[selectinload(AgentRun.resume)],
    )
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
        if run.status == "completed":
            payload = {"locked": run.output_locked}
            yield f"event: done\ndata: {json.dumps(payload)}\n\n"
            return
        if run.status == "failed":
            message = run.error_message or "Run failed"
            yield f"event: error\ndata: {json.dumps({'message': message})}\n\n"
            return

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30.0)
            except TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                continue
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


@router.patch("/{run_id}/variant")
async def patch_run_variant(
    run_id: UUID,
    body: SelectVariantRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    access = AccessService(session)
    if not await access.can_view_output(user.id, run):
        raise HTTPException(status_code=403, detail="Unlock output before selecting a variant")
    try:
        final = await select_variant(session, run, body.variant)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": str(run_id), "selected_variant": body.variant, "final_output": final}


@router.patch("/{run_id}/sections/{section_name}")
async def patch_run_section(
    run_id: UUID,
    section_name: str,
    body: SectionEditRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if section_name not in SECTION_KEYS:
        raise HTTPException(status_code=400, detail="Invalid section")
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    resume = await session.get(MasterResume, run.master_resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    access = AccessService(session)
    if not await access.can_view_output(user.id, run):
        raise HTTPException(status_code=403, detail="Unlock output before editing sections")
    try:
        final = await update_section_override(
            session, run, resume, section=section_name, content=body.content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": str(run_id), "section": section_name, "final_output": final}


@router.post("/{run_id}/sections/{section_name}/add")
async def add_run_section(
    run_id: UUID,
    section_name: str,
    body: AddSectionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    if section_name not in SECTION_KEYS:
        raise HTTPException(status_code=400, detail="Invalid section")
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    resume = await session.get(MasterResume, run.master_resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    access = AccessService(session)
    if not await access.can_view_output(user.id, run):
        raise HTTPException(status_code=403, detail="Unlock output before adding sections")
    if not body.retailor:
        raise HTTPException(status_code=400, detail="retailor=true is required for new sections")
    try:
        final = await add_section_and_retailor(
            session, run, resume, section=section_name, content=body.content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": str(run_id), "section": section_name, "final_output": final}


@router.post("/{run_id}/variants/{variant_name}/generate")
async def generate_run_variant(
    run_id: UUID,
    variant_name: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Run must be completed before generating variants",
        )
    resume = await session.get(MasterResume, run.master_resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    access = AccessService(session)
    if not await access.can_view_output(user.id, run):
        raise HTTPException(status_code=402, detail="Unlock output before generating variants")
    try:
        result = await generate_variant(session, run, resume, variant_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": str(run_id), "variant": variant_name, **result}
