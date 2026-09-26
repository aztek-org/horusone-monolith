"""Trace recorders for persisted training-session provenance events."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_session_event import TrainingSessionEvent


class TraceRecorder(Protocol):
    """Add one immutable provenance event to the caller's unit of work."""

    async def record(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        session_id: int,
        user_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None: ...


class SqlAlchemyTraceRecorder:
    """Persist trace events without taking ownership of the transaction."""

    async def record(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        session_id: int,
        user_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        db.add(
            TrainingSessionEvent(
                session_id=session_id,
                user_id=user_id,
                org_id=org_id,
                event_type=event_type,
                event_payload=payload,
            )
        )


class InMemoryTraceRecorder:
    """Process-local trace recorder used by unit tests."""

    def __init__(self) -> None:
        self.events: list[tuple[int, str, dict[str, Any]]] = []

    async def record(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        session_id: int,
        user_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        del db, org_id, user_id
        self.events.append((session_id, event_type, payload))
