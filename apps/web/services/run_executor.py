from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.web.config import settings
from packages.agent.checkpointer import get_checkpointer
from packages.agent.graph import run_agent
from packages.agent.schemas.providers import DEFAULT_PROVIDER
from packages.agent.service import AgentService
from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.db.models.agent_run import AgentRun
from packages.db.models.agent_run_event import AgentRunEvent
from packages.db.models.resume import MasterResume

_run_queues: dict[str, asyncio.Queue] = {}


def get_run_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def execute_run(session: AsyncSession, run_id: UUID) -> None:
    run = await session.get(AgentRun, run_id)
    if run is None:
        return
    resume = await session.get(MasterResume, run.master_resume_id)
    if resume is None:
        run.status = "failed"
        run.error_message = "Resume not found"
        await session.commit()
        return

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.commit()

    queue = get_run_queue(str(run_id))
    access = AccessService(session)
    decision = await access.can_start_run(run.user_id)
    output_locked = decision.mode == RunAccessMode.LOCKED
    is_free = decision.mode == RunAccessMode.FREE

    provider_name = run.llm_provider or DEFAULT_PROVIDER.value
    agent_service = AgentService(provider_name)

    initial = {
        "run_id": str(run_id),
        "user_id": str(run.user_id),
        "llm_provider": provider_name,
        "master_resume_text": resume.raw_text,
        "jd_text": run.jd_text,
        "output_locked": output_locked,
        "retry_count": 0,
    }

    async def on_progress(item: dict) -> None:
        await queue.put(item)

    try:
        async with get_checkpointer(settings.database_url) as checkpointer:
            result = await run_agent(
                initial,
                agent_service,
                on_progress=on_progress,
                checkpointer=checkpointer,
            )
        run.final_output = result.get("final_output")
        run.preview_text = (result.get("preview_text") or "")[:500]
        match_before = (result.get("match_score_before") or {}).get("overall")
        match_after = (result.get("match_score_after") or {}).get("overall")
        run.ats_score_before = Decimal(str(match_before or result.get("ats_score_before", 0)))
        run.ats_score_after = Decimal(str(match_after or result.get("ats_score_after", 0)))
        run.output_locked = output_locked
        run.is_free_trial_run = is_free
        run.status = "failed" if result.get("fatal_error") else "completed"
        run.error_message = result.get("fatal_error")
        run.completed_at = datetime.now(UTC)
        if is_free and run.status == "completed":
            await access.mark_free_trial_used(run.user_id)
        session.add(
            AgentRunEvent(
                run_id=run_id,
                node_name="graph",
                event_type="completed",
                payload={
                    "locked": output_locked,
                    "llm_provider": provider_name,
                    "match_score_before": float(run.ats_score_before),
                    "match_score_after": float(run.ats_score_after),
                },
            )
        )
        await queue.put({"event": "done", "locked": output_locked})
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        await queue.put({"event": "error", "message": str(exc)})
    await session.commit()
