from __future__ import annotations

import asyncio
from collections.abc import Callable

from apps.web.services.run_executor import get_run_queue

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
    on_update("Run started — preparing inputs", progress_value)

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
        except TimeoutError:
            on_update(
                "Still working… LLM steps can take several minutes",
                progress_value,
            )
            continue

        event = item.get("event")
        if event in ("node_start", "node_complete"):
            node = str(item.get("node") or "step")
            verb = "Started" if event == "node_start" else "Done"
            label = f"{verb}: {steps.get(node, node)}"
            progress_value = min(progress_value + step_increment, 0.92)
            on_update(label, progress_value)
        elif event == "done":
            on_update("Run complete", 1.0)
            return "done"
        elif event == "error":
            on_update(str(item.get("message") or "Run failed"), progress_value)
            return "error"
