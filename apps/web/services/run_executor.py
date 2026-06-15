from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agent.checkpointer import get_checkpointer
from packages.agent.graph import run_agent
from packages.core.access.service import AccessService
from packages.core.schemas.access import RunAccessMode
from packages.db.models.agent_run import AgentRun
from packages.db.models.agent_run_event import AgentRunEvent
from packages.db.models.resume import MasterResume
from apps.web.config import settings
from packages.integrations.hf_inference import complete as hf_complete

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

    initial = {
        "run_id": str(run_id),
        "user_id": str(run.user_id),
        "master_resume_text": resume.raw_text,
        "jd_text": run.jd_text,
        "output_locked": output_locked,
        "retry_count": 0,
    }

    async def llm_complete(*, model: str, prompt: str, node: str) -> str:
        await queue.put({"event": "node_start", "node": node})
        result = await hf_complete(model=model, prompt=prompt, node=node)
        await queue.put({"event": "node_complete", "node": node})
        return result

    try:
        async with get_checkpointer(settings.database_url) as checkpointer:
            result = await run_agent(initial, llm_complete, checkpointer=checkpointer)
        run.final_output = result.get("final_output")
        run.preview_text = (result.get("preview_text") or "")[:500]
        run.ats_score_before = Decimal(str(result.get("ats_score_before", 0)))
        run.ats_score_after = Decimal(str(result.get("ats_score_after", 0)))
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
                payload={"locked": output_locked},
            )
        )
        await queue.put({"event": "done", "locked": output_locked})
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        await queue.put({"event": "error", "message": str(exc)})
    await session.commit()
