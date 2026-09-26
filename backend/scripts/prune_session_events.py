"""Cron entry point for pruning expired training-session provenance events."""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.session import get_session_factory
from app.services.training_sessions.retention import prune_old_events


async def main() -> None:
    """Prune events using the configured trace retention window."""
    async with get_session_factory()() as db:
        removed = await prune_old_events(db, get_settings().trace.retention_days)
        await db.commit()
        print(removed)


if __name__ == "__main__":
    asyncio.run(main())
