"""Public command and result types for the training Session module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.knowledge import Citation


@dataclass(frozen=True)
class StartSessionCommand:
    """Inputs required to begin a persisted training session."""

    org_id: uuid.UUID | None
    user_id: uuid.UUID | None
    session_id: int
    scene_version: str
    language: str
    flight_plan: dict[str, Any]


@dataclass(frozen=True)
class SendTransmissionCommand:
    """One pilot transmission and optional live-context updates."""

    org_id: uuid.UUID | None
    session_id: int
    pilot_message: str
    context_overrides: dict[str, Any] | None = None


@dataclass(frozen=True)
class EndSessionCommand:
    """Inputs required to score and complete a training session."""

    org_id: uuid.UUID | None
    session_id: int
    student_stats_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExchangeResult:
    """Caller-facing result of one live ATC exchange."""

    atc_response: str
    is_emergency: bool
    exchange_count: int
    pending_instructor: bool
    citations: list[Citation]
    provider: str
    model: str
    fallback_used: bool


@dataclass(frozen=True)
class SessionSnapshot:
    """Persisted phase, continuity counter, and graph-internal state."""

    session_id: int
    phase: str
    exchange_count: int
    state: dict[str, Any]


@dataclass(frozen=True)
class Debrief:
    """Scoring and report produced when a session ends."""

    scoring: dict[str, Any]
    badges_earned: list[str]
    report: str


class SessionModule(Protocol):
    """Narrow lifecycle interface consumed by HTTP and voice adapters."""

    async def start(self, command: StartSessionCommand) -> SessionSnapshot: ...

    async def validate(
        self,
        *,
        user_id: uuid.UUID | None,
        flight_plan: dict[str, Any],
        language: str = "en",
        org_id: uuid.UUID | None = None,
    ) -> SessionSnapshot: ...

    async def send(self, command: SendTransmissionCommand) -> ExchangeResult: ...

    async def await_instructor(
        self,
        org_id: uuid.UUID | None,
        session_id: int,
        instructor_response: str | None = None,
    ) -> ExchangeResult | None: ...

    async def end(self, command: EndSessionCommand) -> Debrief: ...

    async def snapshot(self, org_id: uuid.UUID | None, session_id: int) -> SessionSnapshot: ...
