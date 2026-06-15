from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_current_user, get_db
from packages.core.access.service import AccessService
from packages.db.models.resume import MasterResume
from packages.db.models.user import User
from packages.export.pdf_ingest import extract_text_from_upload
from packages.integrations.s3_storage import upload_bytes

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("")
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    access = AccessService(session)
    if not await access.can_upload_resume(user.id):
        raise HTTPException(status_code=402, detail="Upload requires payment after free trial")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    filename = file.filename or "resume.pdf"
    try:
        text = extract_text_from_upload(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    key = f"resumes/{user.id}/{uuid.uuid4()}/{filename}"
    upload_bytes(key, data, file.content_type or "application/octet-stream")
    snap = await access.get_snapshot(user.id)
    resume = MasterResume(
        user_id=user.id,
        filename=filename,
        s3_key=key,
        raw_text=text,
        is_free_trial_resume=not snap.free_trial_used,
    )
    session.add(resume)
    await session.commit()
    return {"resume_id": str(resume.id), "filename": filename}


@router.get("")
async def list_resumes(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(MasterResume).where(MasterResume.user_id == user.id).order_by(MasterResume.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "resumes": [
            {"resume_id": str(r.id), "filename": r.filename, "created_at": r.created_at.isoformat()}
            for r in rows
        ]
    }
