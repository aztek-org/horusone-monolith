"""Route-owned audit events for the training session lifecycle.

Every persisted ``TrainingSession`` must be explained by a ``created`` event, so
the HTTP and WebSocket routes write that event through this one helper rather
than each building their own.  The compensating *delete* lives here for the same
reason: a route that cannot be started is removed through one helper, so neither
route module becomes a library the other imports.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent

logger = logging.getLogger(__name__)


def record_session_event(
    db: AsyncSession,
    *,
    session_id: int,
    user_id: uuid.UUID | None,
    org_id: uuid.UUID | None,
    event_type: str,
    event_payload: dict[str, Any],
) -> TrainingSessionEvent:
    """Add one audit event to the caller's unit of work."""
    event = TrainingSessionEvent(
        session_id=session_id,
        user_id=user_id,
        org_id=org_id,
        event_type=event_type,
        event_payload=event_payload,
    )
    db.add(event)
    return event


def record_session_created(
    db: AsyncSession,
    training_session: TrainingSession,
    *,
    user_id: uuid.UUID | None,
) -> TrainingSessionEvent:
    """Record the ``created`` event that every training session must carry."""
    return record_session_event(
        db,
        session_id=training_session.id,
        user_id=user_id,
        org_id=training_session.org_id,
        event_type="created",
        event_payload={
            "scenario_id": training_session.scenario_id,
            "language": training_session.language,
            "status": training_session.status,
            "scene_version": training_session.scene_version,
        },
    )


async def discard_unstarted_session(db_session_id: int) -> None:
    """Remove a session row that could not be started, so no orphan is left behind.

    The row must be committed before the Session module can record anything
    against it, so a failed start is compensated for by deleting the row here
    rather than leaving a session that claims to exist but was never started.
    Both creation paths — the HTTP route and the voice WebSocket — compensate the
    same way through this one helper.
    """
    from app.db.session import get_session_factory

    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            await db.execute(delete(TrainingSession).where(TrainingSession.id == db_session_id))
            await db.commit()
    except Exception as e:
        logger.warning("Could not discard training session %s: %s", db_session_id, e)
