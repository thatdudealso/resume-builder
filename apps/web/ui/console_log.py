from __future__ import annotations

import json
from typing import Any

from nicegui import ui


def log_console(message: str, *, level: str = "log", **data: Any) -> None:
    payload = json.dumps({"message": message, **data})
    ui.run_javascript(f'console.{level}("[ResumeBuilder]", {payload})')
