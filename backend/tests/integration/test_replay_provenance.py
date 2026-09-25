"""Integration tests for provenance in the session replay response."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import get_authenticated_user


class _Result:
    def __init__(self, *, training_session=None, events=None):
        self._training_session = training_session
        self._events = events or []

    def scalar_one_or_none(self):
        return self._training_session

    def scalars(self):
        return SimpleNamespace(all=lambda: self._events)


class _DummySession:
    def __init__(self, training_session=None, events=None):
        self._training_session = training_session
        self._events = events or []
        self.execute_count = 0

    async def execute(self, *_args, **_kwargs):
        self.execute_count += 1
        if self.execute_count == 1:
            return _Result(training_session=self._training_session)
        return _Result(events=self._events)


def _override_auth(local_user_id: uuid.UUID) -> None:
    token_user = TokenUser(
        keycloak_id="kc-test",
        email="pilot@test.com",
        display_name="Test Pilot",
        roles=["student"],
        organization_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: token_user

    async def _get_local_user():
        return SimpleNamespace(id=local_user_id)

    app.dependency_overrides[get_authenticated_user] = _get_local_user


def _override_db(db_session: _DummySession) -> None:
    async def _get_db():
        return db_session

    app.dependency_overrides[get_db_session] = _get_db


def test_replay_includes_real_and_legacy_event_provenance(
    client: TestClient,
) -> None:
    local_user_id = uuid.uuid4()
    created_at = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    training_session = SimpleNamespace(
        id=42,
        scenario_id=7,
        scenario=SimpleNamespace(name="JFK Departure"),
        status="completed",
        language="en",
        started_at=created_at,
        ended_at=None,
        user_id=local_user_id,
        org_id=uuid.uuid4(),
        voice_logs=[],
    )
    events = [
        SimpleNamespace(
            event_type="created",
            event_payload={
                "scenario_id": 7,
                "language": "en",
                "status": "active",
                "scene_version": "atc-2026.09",
            },
            created_at=created_at,
        ),
        SimpleNamespace(
            event_type="exchange_completed",
            event_payload={
                "graph": "live",
                "node": "generate_atc_response",
                "scene_version": "atc-2026.09",
                "prompt_version": "atc-2026.09",
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "fallback_used": True,
                "retrieved_chunk_ids": ["chunk-a", "chunk-b"],
                "instructor_overridden": False,
                "org_id": str(training_session.org_id),
                "session_id": 42,
            },
            created_at=created_at.replace(microsecond=1),
        ),
    ]
    db_session = _DummySession(training_session, events)
    _override_auth(local_user_id)
    _override_db(db_session)

    with (
        patch(
            "app.api.v1.sessions.waypoint_repo.get_session_track",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.sessions.waypoint_repo.get_flight_insights",
            new=AsyncMock(return_value=[]),
        ),
    ):
        response = client.get("/api/v1/sessions/42/replay")

    assert response.status_code == 200
    assert response.json()["provenance"] == [
        {
            "event_type": "created",
            "created_at": "2026-09-25T12:00:00Z",
            "graph": None,
            "node": None,
            "scene_version": "atc-2026.09",
            "prompt_version": None,
            "llm_provider": None,
            "llm_model": None,
            "llm_fallback_used": None,
            "retrieved_chunk_ids": [],
            "instructor_overridden": None,
        },
        {
            "event_type": "exchange_completed",
            "created_at": "2026-09-25T12:00:00.000001Z",
            "graph": "live",
            "node": "generate_atc_response",
            "scene_version": "atc-2026.09",
            "prompt_version": "atc-2026.09",
            "llm_provider": "groq",
            "llm_model": "llama-3.3-70b-versatile",
            "llm_fallback_used": True,
            "retrieved_chunk_ids": ["chunk-a", "chunk-b"],
            "instructor_overridden": False,
        },
    ]


def test_replay_does_not_query_events_for_unauthorized_session(
    client: TestClient,
) -> None:
    training_session = SimpleNamespace(
        id=8,
        scenario_id=None,
        scenario=None,
        status="active",
        language="en",
        started_at=datetime.now(timezone.utc),
        ended_at=None,
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        voice_logs=[],
    )
    db_session = _DummySession(training_session)
    _override_auth(uuid.uuid4())
    _override_db(db_session)

    response = client.get("/api/v1/sessions/8/replay")

    assert response.status_code == 403
    assert db_session.execute_count == 1
