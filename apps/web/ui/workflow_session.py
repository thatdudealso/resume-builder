from __future__ import annotations

import json
from typing import Any

from nicegui import ui

SESSION_STORAGE_KEY = "rb_workflow"

WORKFLOW_SESSION_SCRIPT = """
<script>
  window.rbWorkflowSession = {
    key: "rb_workflow",
    save(payload) {
      sessionStorage.setItem(this.key, JSON.stringify(payload));
    },
    load() {
      const raw = sessionStorage.getItem(this.key);
      if (!raw) return null;
      try { return JSON.parse(raw); } catch (_) { return null; }
    },
    clear() {
      sessionStorage.removeItem(this.key);
    }
  };
</script>
"""


async def ensure_device_fingerprint() -> None:
    await ui.run_javascript("window.rbFingerprint.get();")


async def load_browser_workflow() -> dict[str, Any] | None:
    raw = await ui.run_javascript(
        f"return sessionStorage.getItem({json.dumps(SESSION_STORAGE_KEY)});"
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def save_browser_workflow(*, run_id: str, resume_id: str | None, jd_text: str) -> None:
    payload = json.dumps({"run_id": run_id, "resume_id": resume_id, "jd_text": jd_text})
    await ui.run_javascript(
        f"sessionStorage.setItem({json.dumps(SESSION_STORAGE_KEY)}, {json.dumps(payload)});"
    )


async def clear_browser_workflow() -> None:
    await ui.run_javascript(f"sessionStorage.removeItem({json.dumps(SESSION_STORAGE_KEY)});")


def merge_query_workflow_state(
    state: dict[str, Any],
    query: dict[str, str],
    stored: dict[str, Any] | None,
) -> None:
    if query.get("run_id"):
        state["run_id"] = query["run_id"]
    elif stored and stored.get("run_id"):
        state["run_id"] = stored["run_id"]

    if query.get("resume_id"):
        state["resume_id"] = query["resume_id"]
    elif stored and stored.get("resume_id"):
        state["resume_id"] = stored["resume_id"]

    if stored and stored.get("jd_text") and not state.get("jd_text"):
        state["jd_text"] = stored["jd_text"]


def apply_run_context(state: dict[str, Any], body: dict[str, Any]) -> None:
    if body.get("master_resume_id"):
        state["resume_id"] = body["master_resume_id"]
    if body.get("jd_text"):
        state["jd_text"] = body["jd_text"]
