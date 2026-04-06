"""Unit tests for session lifecycle audit events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.v1 import sessions
from app.middleware.auth import TokenUser
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.schemas.training_session import TrainingSessionCreate


class _SessionResult:
    """Simple SQLAlchemy result stub with scalar_one_or_none support."""

    def __init__(self, training_session: object | None) -> None:
        self._training_session = training_session

    def scalar_one_or_none(self) -> object | None:
        return self._training_session


class _EventsResult:
    """Simple SQLAlchemy result stub with scalars().all() support."""

    def __init__(self, events: list[object]) -> None:
        self._events = events

    def scalars(self) -> _EventsResult:
        return self

    def all(self) -> list[object]:
        return self._events


def _build_student(org_id: uuid.UUID) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-student",
        email="student@test.com",
        display_name="Student",
        roles=["student"],
        organization_id=str(org_id),
    )


@pytest.mark.asyncio
async def test_create_session_records_created_event() -> None:
    """Creating a session should append a created audit event."""
    org_id = uuid.uuid4()
    local_user_id = uuid.uuid4()
    session = AsyncMock()
    session.add = Mock()

    async def _refresh(instance: object) -> None:
        if isinstance(instance, TrainingSession):
            instance.id = 77

    session.refresh = AsyncMock(side_effect=_refresh)

    await sessions.create_session(
        data=TrainingSessionCreate(scenario_id=3, language="en"),
        user=_build_student(org_id),
        _seat=object(),
        org_id=org_id,
        local_user=SimpleNamespace(id=local_user_id),
        session=session,
    )

    added = [call.args[0] for call in session.add.call_args_list]
    created_event = next(item for item in added if isinstance(item, TrainingSessionEvent))
    assert created_event.event_type == "created"
    assert created_event.session_id == 77
    assert created_event.user_id == local_user_id
    assert created_event.org_id == org_id


@pytest.mark.asyncio
async def test_complete_session_records_completed_event() -> None:
    """Completing an active session should append a completed audit event."""
    org_id = uuid.uuid4()
    local_user_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    training_session = SimpleNamespace(
        id=42,
        scenario_id=7,
        status="active",
        language="en",
        started_at=now,
        ended_at=None,
        user_id=local_user_id,
        org_id=org_id,
    )
    session = AsyncMock()
    session.add = Mock()
    session.execute = AsyncMock(return_value=_SessionResult(training_session))

    scoring_payload = {
        "scoring": {
            "communication_score": 90,
            "decision_score": 88,
            "procedure_score": 92,
            "overall_score": 90,
            "grade": "A",
            "strengths": [],
            "improvements": [],
            "summary": "Great run",
        },
        "badges_earned": ["clean-ops"],
        "report": "Session complete",
    }

    with patch("app.api.v1.sessions._run_scoring", new=AsyncMock(return_value=scoring_payload)):
        await sessions.complete_session(
            session_id=42,
            user=_build_student(org_id),
            local_user=SimpleNamespace(id=local_user_id),
            session=session,
        )

    added = [call.args[0] for call in session.add.call_args_list]
    completed_event = next(item for item in added if isinstance(item, TrainingSessionEvent))
    assert completed_event.event_type == "completed"
    assert completed_event.event_payload["grade"] == "A"
    assert completed_event.event_payload["overall_score"] == 90.0


@pytest.mark.asyncio
async def test_get_session_events_returns_session_audit_entries() -> None:
    """Session events endpoint should return ordered audit records."""
    org_id = uuid.uuid4()
    local_user_id = uuid.uuid4()
    session_id = 9
    session = AsyncMock()
    training_session = SimpleNamespace(
        id=session_id,
        user_id=local_user_id,
        org_id=org_id,
    )
    events = [
        SimpleNamespace(
            id=uuid.uuid4(),
            session_id=session_id,
            user_id=local_user_id,
            org_id=org_id,
            event_type="created",
            event_payload={"status": "active"},
            created_at=datetime.now(tz=timezone.utc),
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            session_id=session_id,
            user_id=local_user_id,
            org_id=org_id,
            event_type="completed",
            event_payload={"grade": "B"},
            created_at=datetime.now(tz=timezone.utc),
        ),
    ]
    session.execute = AsyncMock(
        side_effect=[_SessionResult(training_session), _EventsResult(events)]
    )

    result = await sessions.get_session_events(
        session_id=session_id,
        user=_build_student(org_id),
        local_user=SimpleNamespace(id=local_user_id),
        session=session,
    )

    assert len(result) == 2
    assert result[0].event_type == "created"
    assert result[1].event_type == "completed"
