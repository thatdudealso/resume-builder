from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.dependencies import get_current_user, get_db
from packages.db.models.resume import MasterResume
from packages.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    from packages.core.access.service import AccessService

    snap = await AccessService(session).get_snapshot(user.id)
    resume_count = await session.execute(
        select(func.count()).select_from(MasterResume).where(MasterResume.user_id == user.id)
    )
    can_upload = (resume_count.scalar() or 0) < 1 or snap.has_confirmed_payment
    return {
        "user": {"id": str(user.id), "email": user.email},
        "free_trial_used": snap.free_trial_used,
        "can_upload": can_upload,
    }
