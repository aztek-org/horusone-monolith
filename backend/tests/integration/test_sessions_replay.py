"""Integration tests for session replay endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import get_authenticated_user


class _SessionResult:
    """Simple result proxy for session and event queries."""

    def __init__(
        self,
        training_session: object | None = None,
        events: list[object] | None = None,
    ) -> None:
        self._training_session = training_session
        self._events = events or []

    def scalar_one_or_none(self) -> object | None:
        return self._training_session

    def scalars(self) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: self._events)


class _DummySession:
    """Tiny async session stub for endpoint testing."""

    def __init__(
        self,
        training_session: object | None,
        events: list[object] | None = None,
    ) -> None:
        self.training_session = training_session
        self.events = events or []
        self.execute_count = 0

    async def execute(self, *_args, **_kwargs) -> _SessionResult:
        self.execute_count += 1
        if self.execute_count == 1:
            return _SessionResult(training_session=self.training_session)
        return _SessionResult(events=self.events)


def _override_auth(local_user_id: uuid.UUID, roles: list[str] | None = None) -> None:
    token_user = TokenUser(
        keycloak_id="kc-test",
        email="pilot@test.com",
        display_name="Test Pilot",
        roles=roles or ["student"],
        organization_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: token_user

    async def _get_local_user() -> SimpleNamespace:
        return SimpleNamespace(id=local_user_id)

    app.dependency_overrides[get_authenticated_user] = _get_local_user


def _override_db(training_session: object | None) -> None:
    db_session = _DummySession(training_session)

    async def _get_db() -> _DummySession:
        return db_session

    app.dependency_overrides[get_db_session] = _get_db


def test_get_session_replay_returns_aggregated_payload(client: TestClient) -> None:
    """Replay endpoint returns normalized track/insight/log payload."""
    local_user_id = uuid.uuid4()
    started_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ended_at = started_at + timedelta(minutes=20)

    training_session = SimpleNamespace(
        id=42,
        scenario_id=7,
        scenario=SimpleNamespace(name="JFK Departure"),
        status="completed",
        language="en",
        started_at=started_at,
        ended_at=ended_at,
        user_id=local_user_id,
        org_id=uuid.uuid4(),
        voice_logs=[
            SimpleNamespace(
                id=1,
                role="pilot",
                transcript="JFK Tower, N123AB ready for departure",
                created_at=started_at + timedelta(seconds=20),
            ),
            SimpleNamespace(
                id=2,
                role="atc",
                transcript="N123AB, cleared for takeoff runway 31L",
                created_at=started_at + timedelta(seconds=45),
            ),
        ],
    )
    track_points = [
        {
            "timestamp": started_at.isoformat(),
            "lat": 40.64,
            "lon": -73.78,
            "altitude_ft": 15,
            "speed_kts": 0,
            "heading_deg": 315,
            "vertical_speed_fpm": 0,
            "phase": "ground",
        },
        {
            "timestamp": (started_at + timedelta(seconds=60)).isoformat(),
            "lat": 40.66,
            "lon": -73.79,
            "altitude_ft": 850,
            "speed_kts": 145,
            "heading_deg": 320,
            "vertical_speed_fpm": 1800,
            "phase": "departure",
        },
    ]
    insights = [
        SimpleNamespace(
            id=uuid.uuid4(),
            type="communication",
            severity="medium",
            title="Readback delay",
            description="Pilot readback was slightly delayed.",
            timestamp_in_session=30.0,
        )
    ]

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    with (
        patch(
            "app.api.v1.sessions.waypoint_repo.get_session_track",
            new=AsyncMock(return_value=SimpleNamespace(track_points=track_points)),
        ),
        patch(
            "app.api.v1.sessions.waypoint_repo.get_flight_insights",
            new=AsyncMock(return_value=insights),
        ),
    ):
        response = client.get("/api/v1/sessions/42/replay")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["scenario_name"] == "JFK Departure"
    assert data["duration_seconds"] == 1200
    assert len(data["track_points"]) == 2
    assert data["voice_logs"][0]["speaker"] == "pilot"
    assert data["insights"][0]["category"] == "communication"
    assert data["scoring"] is not None


def test_get_session_replay_returns_404_when_session_missing(client: TestClient) -> None:
    """Replay endpoint returns 404 when session does not exist."""
    _override_auth(uuid.uuid4(), roles=["student"])
    _override_db(None)

    response = client.get("/api/v1/sessions/999/replay")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_session_replay_returns_403_for_unauthorized_user(client: TestClient) -> None:
    """Replay endpoint denies users who do not own the session."""
    local_user_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    training_session = SimpleNamespace(
        id=8,
        scenario_id=None,
        scenario=None,
        status="active",
        language="en",
        started_at=now - timedelta(minutes=5),
        ended_at=None,
        user_id=owner_user_id,
        org_id=uuid.uuid4(),
        voice_logs=[],
    )

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    response = client.get("/api/v1/sessions/8/replay")

    assert response.status_code == 403
    assert "do not have access" in response.json()["detail"].lower()
