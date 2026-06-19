from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from apps.web.services.run_executor import get_run_queue

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]


async def watch_run_progress(
    run_id: str,
    *,
    steps: dict[str, str],
    on_update: ProgressCallback,
    step_increment: float = 0.18,
) -> str:
    """Subscribe to the in-process run queue (avoids HTTP SSE self-deadlock).

    Returns ``done`` or ``error``.
    """
    queue = get_run_queue(run_id)
    progress_value = 0.1
    logger.info("watch_run_progress subscribed run_id=%s", run_id)
    on_update("Run started — preparing inputs", progress_value)

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except TimeoutError:
            logger.warning("watch_run_progress timeout run_id=%s progress=%.2f", run_id, progress_value)
            on_update(
                "Still working… LLM steps can take several minutes",
                progress_value,
            )
            continue

        event = item.get("event")
        logger.info("watch_run_progress event run_id=%s payload=%s", run_id, item)
        if event in ("node_start", "node_complete"):
            node = str(item.get("node") or "step")
            verb = "Started" if event == "node_start" else "Done"
            label = f"{verb}: {steps.get(node, node)}"
            progress_value = min(progress_value + step_increment, 0.92)
            on_update(label, progress_value)
        elif event == "done":
            logger.info("watch_run_progress done run_id=%s", run_id)
            on_update("Run complete", 1.0)
            return "done"
        elif event == "error":
            logger.error(
                "watch_run_progress error run_id=%s message=%s",
                run_id,
                item.get("message"),
            )
            on_update(str(item.get("message") or "Run failed"), progress_value)
            return "error"
