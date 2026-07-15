from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from apps.web.config import settings
from packages.core.schemas.access import AccessSnapshot, RunAccessDecision, RunAccessMode
from packages.db.models.agent_run import AgentRun
from packages.db.models.payment import Payment
from packages.db.models.resume import MasterResume
from packages.db.models.user import User


class AccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def payment_window_started_at(payment: Payment) -> datetime | None:
        return payment.confirmed_at or payment.created_at

    @staticmethod
    def payment_window_expires_at(payment: Payment) -> datetime | None:
        started_at = AccessService.payment_window_started_at(payment)
        if started_at is None:
            return None
        return started_at + timedelta(hours=24)

    def _active_payment_predicate(self) -> ColumnElement[bool]:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        return and_(
            Payment.status == "confirmed",
            or_(
                Payment.confirmed_at >= cutoff,
                and_(Payment.confirmed_at.is_(None), Payment.created_at >= cutoff),
            ),
        )

    async def get_user(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def has_confirmed_payment(self, user_id: UUID) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(Payment)
            .where(Payment.user_id == user_id, Payment.status == "confirmed")
        )
        return (result.scalar() or 0) > 0

    async def get_active_payment(self, user_id: UUID) -> Payment | None:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id, self._active_payment_predicate())
            .order_by(Payment.confirmed_at.desc().nullslast(), Payment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_active_payment_window(self, user_id: UUID) -> bool:
        return await self.get_active_payment(user_id) is not None

    async def get_snapshot(self, user_id: UUID) -> AccessSnapshot:
        user = await self.get_user(user_id)
        if user is None:
            raise ValueError("User not found")
        has_payment = await self.has_active_payment_window(user_id)
        can_upload = not user.free_trial_used or has_payment
        return AccessSnapshot(
            user_id=user_id,
            free_trial_used=user.free_trial_used,
            has_confirmed_payment=has_payment,
            can_upload=can_upload,
        )

    async def can_upload_resume(self, user_id: UUID) -> bool:
        if not settings.payments_enabled:
            return True
        if await self.has_active_payment_window(user_id):
            return True

        result = await self.session.execute(
            select(func.count())
            .select_from(MasterResume)
            .where(MasterResume.user_id == user_id)
        )
        count = result.scalar() or 0
        return count < 1

    async def can_start_run(self, user_id: UUID) -> RunAccessDecision:
        user = await self.get_user(user_id)
        if user is None:
            return RunAccessDecision(mode=RunAccessMode.BLOCKED, message="User not found")
        if not settings.payments_enabled:
            return RunAccessDecision(mode=RunAccessMode.FREE)
        if not user.free_trial_used:
            return RunAccessDecision(mode=RunAccessMode.FREE)
        if await self.has_active_payment_window(user_id):
            return RunAccessDecision(mode=RunAccessMode.PAID)
        return RunAccessDecision(
            mode=RunAccessMode.LOCKED,
            message="Output will be locked until payment.",
        )

    async def can_view_output(self, user_id: UUID, run: AgentRun) -> bool:
        if run.user_id != user_id:
            return False
        if not settings.payments_enabled:
            return True
        if not run.output_locked:
            return True
        if run.payment_id:
            payment = await self.session.get(Payment, run.payment_id)
            if payment and payment.status == "confirmed":
                return True
        result = await self.session.execute(
            select(Payment)
            .where(
                Payment.run_id == run.id,
                Payment.user_id == user_id,
                Payment.status == "confirmed",
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def can_export(self, user_id: UUID, run: AgentRun) -> bool:
        if not await self.can_view_output(user_id, run):
            return False
        if not settings.payments_enabled:
            return True
        if run.is_free_trial_run:
            return True
        return run.payment_id is not None

    async def unlock_run(self, payment_id: UUID, run_id: UUID) -> None:
        run = await self.session.get(AgentRun, run_id)
        payment = await self.session.get(Payment, payment_id)
        if run is None or payment is None:
            return
        run.output_locked = False
        run.payment_id = payment_id
        payment.status = "confirmed"
        if payment.confirmed_at is None:
            payment.confirmed_at = datetime.now(UTC)
        payment.run_id = run_id
        await self.session.flush()

    async def mark_free_trial_used(self, user_id: UUID) -> None:
        user = await self.get_user(user_id)
        if user and not user.free_trial_used:
            user.free_trial_used = True
            await self.session.flush()
