from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class RunAccessMode(StrEnum):
    FREE = "free"
    LOCKED = "locked"
    BLOCKED = "blocked"


class RunAccessDecision(BaseModel):
    mode: RunAccessMode
    message: str = ""


class AccessSnapshot(BaseModel):
    user_id: UUID
    free_trial_used: bool
    has_confirmed_payment: bool
    can_upload: bool
