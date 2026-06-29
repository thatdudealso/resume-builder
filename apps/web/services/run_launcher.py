from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.services.run_executor import execute_run, get_run_queue
from packages.agent.providers.registry import get_provider
from packages.agent.schemas.providers import LLMProviderName
from packages.agent.schemas.variants import VariantName
from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessDecision, RunAccessMode
from packages.core.security.sanitization import sanitize_text
from packages.db.models.agent_run import AgentRun
from packages.db.models.resume import MasterResume
from packages.db.models.user import User

logger = logging.getLogger(__name__)


class RunLaunchError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def create_run_record(
    session: AsyncSession,
    user: User,
    *,
    resume_id: UUID,
    jd_text: str,
    llm_provider: str,
    variant: str,
) -> dict[str, object]:
    logger.info(
        "create_run_record user=%s resume=%s provider=%s variant=%s jd_chars=%s",
        user.id,
        resume_id,
        llm_provider,
        variant,
        len(jd_text),
    )
    resume = await session.get(MasterResume, resume_id)
    if resume is None or resume.user_id != user.id:
        raise RunLaunchError(404, "Resume not found")
    try:
        provider_name = LLMProviderName(llm_provider)
    except ValueError as exc:
        raise RunLaunchError(400, "Invalid llm_provider") from exc
    provider = get_provider(provider_name)
    if not provider.is_configured():
        raise RunLaunchError(
            400,
            f"LLM provider '{provider_name.value}' is not configured",
        )
    try:
        variant_name = VariantName(variant)
    except ValueError as exc:
        raise RunLaunchError(400, "Invalid variant") from exc
    access = AccessService(session)
    decision = await access.can_start_run(user.id)
    if decision.mode == RunAccessMode.BLOCKED:
        raise RunLaunchError(403, decision.message)
    active_payment = None
    if decision.mode == RunAccessMode.PAID:
        active_payment = await access.get_active_payment(user.id)
        if active_payment is None:
            decision = RunAccessDecision(
                mode=RunAccessMode.LOCKED,
                message="Payment window expired. Output will be locked until payment.",
            )
    jd = sanitize_text(jd_text)
    run = AgentRun(
        user_id=user.id,
        master_resume_id=resume.id,
        jd_text=jd,
        llm_provider=provider_name.value,
        output_locked=decision.mode == RunAccessMode.LOCKED,
        is_free_trial_run=decision.mode == RunAccessMode.FREE,
        payment_id=active_payment.id if active_payment else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    run_id = str(run.id)
    get_run_queue(run_id)
    logger.info("Run persisted run_id=%s status=%s", run_id, run.status)
    return {
        "run_id": run_id,
        "status": run.status,
        "output_locked": run.output_locked,
        "llm_provider": run.llm_provider,
        "variant": variant_name.value,
    }


async def execute_run_background(run_id: UUID, variant: str | None = None) -> None:
    from packages.db.session import SessionLocal

    logger.info("Background execution starting run_id=%s variant=%s", run_id, variant)
    try:
        async with SessionLocal() as session:
            await execute_run(session, run_id, variant=variant)
        logger.info("Background execution finished run_id=%s", run_id)
    except Exception:
        logger.exception("Background execution failed run_id=%s", run_id)


async def create_and_schedule_run(
    session: AsyncSession,
    user: User,
    *,
    resume_id: UUID,
    jd_text: str,
    llm_provider: str,
    variant: str,
) -> dict[str, object]:
    result = await create_run_record(
        session,
        user,
        resume_id=resume_id,
        jd_text=jd_text,
        llm_provider=llm_provider,
        variant=variant,
    )
    asyncio.create_task(
        execute_run_background(UUID(str(result["run_id"])), str(result["variant"]))
    )
    return result
