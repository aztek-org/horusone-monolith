"""Retention pruning for persisted training-session provenance events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_session_event import TrainingSessionEvent


async def prune_old_events(db: AsyncSession, retention_days: int) -> int:
    """Delete events older than the retention window and return the row count."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        delete(TrainingSessionEvent).where(TrainingSessionEvent.created_at < cutoff)
    )
    return cast(CursorResult[Any], result).rowcount
