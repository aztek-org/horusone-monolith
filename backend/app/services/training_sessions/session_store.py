"""Storage abstractions for tenant-scoped training session state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class StoredState:
    """Persisted state for a training session."""

    values: dict[str, Any]
    checkpoint_id: str | None
    pending_instructor: bool


class SessionStore(Protocol):
    """Persistence interface for training session state."""

    async def load(self, org_id: uuid.UUID, session_id: int) -> StoredState | None:
        """Load state for a session in an organization."""

    async def save(
        self,
        org_id: uuid.UUID,
        session_id: int,
        state: dict[str, Any],
        pending_instructor: bool = False,
    ) -> StoredState:
        """Save state for a session in an organization."""

    async def delete(self, org_id: uuid.UUID, session_id: int) -> None:
        """Delete state for a session in an organization."""

    @staticmethod
    def thread_id(org_id: uuid.UUID, session_id: int) -> str:
        """Return the tenant-scoped checkpointer thread identifier."""
        return f"{org_id}:{session_id}"


class InMemorySessionStore:
    """Process-local session store used by unit tests."""

    def __init__(self) -> None:
        self._states: dict[str, StoredState] = {}

    @staticmethod
    def thread_id(org_id: uuid.UUID, session_id: int) -> str:
        return SessionStore.thread_id(org_id, session_id)

    async def load(self, org_id: uuid.UUID, session_id: int) -> StoredState | None:
        return self._states.get(SessionStore.thread_id(org_id, session_id))

    async def save(
        self,
        org_id: uuid.UUID,
        session_id: int,
        state: dict[str, Any],
        pending_instructor: bool = False,
    ) -> StoredState:
        stored = StoredState(
            values=dict(state),
            checkpoint_id=None,
            pending_instructor=pending_instructor,
        )
        self._states[SessionStore.thread_id(org_id, session_id)] = stored
        return stored

    async def delete(self, org_id: uuid.UUID, session_id: int) -> None:
        self._states.pop(SessionStore.thread_id(org_id, session_id), None)
