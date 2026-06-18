from __future__ import annotations

import asyncio

import pytest

from apps.web.services.run_executor import get_run_queue
from apps.web.ui.run_progress import watch_run_progress


@pytest.mark.asyncio
async def test_watch_run_progress_receives_queue_events():
    run_id = "test-run-progress"
    queue = get_run_queue(run_id)
    updates: list[tuple[str, float]] = []

    async def producer() -> None:
        await asyncio.sleep(0.05)
        await queue.put({"event": "node_start", "node": "prepare_inputs"})
        await queue.put({"event": "node_complete", "node": "prepare_inputs"})
        await queue.put({"event": "done", "locked": False})

    producer_task = asyncio.create_task(producer())
    result = await watch_run_progress(
        run_id,
        steps={"prepare_inputs": "Reading resume"},
        on_update=lambda label, value: updates.append((label, value)),
    )
    await producer_task

    assert result == "done"
    assert updates[0][0] == "Run started — preparing inputs"
    assert any("Reading resume" in label for label, _ in updates)
    assert updates[-1] == ("Run complete", 1.0)
