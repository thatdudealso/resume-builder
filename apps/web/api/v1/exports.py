from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_current_user, get_db
from packages.core.access.service import AccessService
from packages.db.models.agent_run import AgentRun
from packages.db.models.export import Export
from packages.db.models.resume import MasterResume
from packages.db.models.user import User
from packages.export.docx_export import export_docx, export_txt
from packages.export.pdf_export import export_pdf
from packages.integrations.s3_storage import presigned_url, upload_bytes

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportRequest(BaseModel):
    run_id: UUID
    format: str


@router.post("")
async def create_export(
    body: ExportRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    run = await session.get(AgentRun, body.run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    access = AccessService(session)
    if not await access.can_view_output(user.id, run):
        raise HTTPException(status_code=402, detail="Output locked — payment required")
    if body.format not in ("txt", "docx", "pdf"):
        raise HTTPException(status_code=400, detail="Invalid format")
    if run.is_free_trial_run and body.format != "txt":
        raise HTTPException(status_code=402, detail="Free trial allows TXT export only")
    if not run.is_free_trial_run and body.format == "txt":
        pass
    output = run.final_output or {}
    plain = output.get("plain_text", "")
    if body.format == "txt":
        data = export_txt(plain)
        content_type = "text/plain"
    elif body.format == "docx":
        resume = await session.get(MasterResume, run.master_resume_id)
        style_meta = resume.style_metadata if resume else None
        data = export_docx(plain, style_metadata=style_meta)
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        data = export_pdf(plain)
        content_type = "application/pdf"
    key = f"exports/{user.id}/{run.id}/{uuid.uuid4()}.{body.format}"
    upload_bytes(key, data, content_type)
    export = Export(user_id=user.id, run_id=run.id, format=body.format, s3_key=key)
    session.add(export)
    await session.commit()
    return {"export_id": str(export.id), "download_url": f"/api/v1/exports/{export.id}/download"}


@router.get("/{export_id}/download")
async def download_export(
    export_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    export = await session.get(Export, export_id)
    if export is None or export.user_id != user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    url = presigned_url(export.s3_key)
    from starlette.responses import RedirectResponse

    return RedirectResponse(url)
