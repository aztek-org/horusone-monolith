"""PostgreSQL tests for training-session event retention."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import get_session_factory
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.services.training_sessions.retention import prune_old_events

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="needs Postgres",
)


@pytest.mark.asyncio
async def test_prune_removes_only_old_events() -> None:
    async with get_session_factory()() as db:
        training_session = TrainingSession(
            user_id=None,
            org_id=None,
            language="en",
            status="completed",
        )
        db.add(training_session)
        await db.flush()
        old_event = TrainingSessionEvent(
            session_id=training_session.id,
            event_type="old",
            event_payload={},
            created_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
        new_event = TrainingSessionEvent(
            session_id=training_session.id,
            event_type="new",
            event_payload={},
        )
        db.add_all([old_event, new_event])
        await db.commit()

        try:
            removed = await prune_old_events(db, 90)

            assert removed == 1
            remaining = list(
                (
                    await db.execute(
                        select(TrainingSessionEvent).where(
                            TrainingSessionEvent.session_id == training_session.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert [event.event_type for event in remaining] == ["new"]
        finally:
            await db.execute(
                delete(TrainingSessionEvent).where(
                    TrainingSessionEvent.session_id == training_session.id
                )
            )
            await db.execute(
                delete(TrainingSession).where(TrainingSession.id == training_session.id)
            )
            await db.commit()
