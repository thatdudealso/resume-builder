#!/usr/bin/env python3
"""Seed development data."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main() -> None:
    from packages.core.security.jwt import register_user
    from packages.db.session import SessionLocal

    async with SessionLocal() as session:
        user = await register_user(session, "dev@example.com", "password123")
        await session.commit()
        print(f"Seeded user {user.email}")


if __name__ == "__main__":
    asyncio.run(main())
