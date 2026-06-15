from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base, JsonType, new_uuid


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    master_resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_resumes.id"), nullable=False
    )
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    is_free_trial_run: Mapped[bool] = mapped_column(Boolean, default=False)
    output_locked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))
    ats_score_before: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ats_score_after: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    final_output: Mapped[dict | None] = mapped_column(JsonType)
    preview_text: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="runs")
    resume: Mapped["MasterResume"] = relationship(back_populates="runs")
    payment: Mapped["Payment | None"] = relationship(back_populates="run", foreign_keys=[payment_id])
    events: Mapped[list["AgentRunEvent"]] = relationship(back_populates="run")
    exports: Mapped[list["Export"]] = relationship(back_populates="run")
