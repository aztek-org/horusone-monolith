"""Route-owned audit events for the training session lifecycle.

Every persisted ``TrainingSession`` must be explained by a ``created`` event, so
the HTTP and WebSocket routes write that event through this one helper rather
than each building their own.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent


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
