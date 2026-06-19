#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from apps.web.config import settings
from packages.agent.checkpointer import ensure_checkpointer_schema


async def main() -> None:
    await ensure_checkpointer_schema(settings.database_url)
    print("LangGraph checkpoint schema ready.")


if __name__ == "__main__":
    asyncio.run(main())
