"""Integration tests for session completion endpoint."""

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


class _SessionResult:
    """Simple result proxy that mimics ``scalar_one_or_none``."""

    def __init__(self, training_session: object | None) -> None:
        self._training_session = training_session

    def scalar_one_or_none(self) -> object | None:
        return self._training_session


class _DummySession:
    """Tiny async DB session stub for endpoint testing."""

    def __init__(self, training_session: object | None) -> None:
        self.training_session = training_session
        self.added: list[object] = []

    async def execute(self, *_args, **_kwargs) -> _SessionResult:
        return _SessionResult(self.training_session)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None

    async def refresh(self, _instance: object) -> None:
        return None


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


def _make_training_session(
    *,
    session_id: int,
    owner_user_id: uuid.UUID,
    status: str,
    ended_at: datetime | None,
) -> SimpleNamespace:
    now = datetime.now(tz=timezone.utc)
    return SimpleNamespace(
        id=session_id,
        scenario_id=7,
        scenario=None,
        status=status,
        language="en",
        started_at=now,
        ended_at=ended_at,
        user_id=owner_user_id,
        org_id=uuid.uuid4(),
        voice_logs=[],
    )


def test_complete_session_marks_active_session_completed(client: TestClient) -> None:
    """Completing an active session returns scoring and replay link."""
    local_user_id = uuid.uuid4()
    training_session = _make_training_session(
        session_id=42,
        owner_user_id=local_user_id,
        status="active",
        ended_at=None,
    )

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    scoring_payload = {
        "scoring": {
            "communication_score": 90,
            "decision_score": 88,
            "procedure_score": 92,
            "overall_score": 90,
            "grade": "A",
            "strengths": ["Good phraseology"],
            "improvements": ["Reduce hesitation on readback"],
            "summary": "Strong overall mission performance.",
        },
        "badges_earned": ["clean-ops"],
        "report": "Mission completed successfully.",
    }

    with patch(
        "app.api.v1.sessions._run_scoring",
        new=AsyncMock(return_value=scoring_payload),
    ):
        response = client.post("/api/v1/sessions/42/complete")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == 42
    assert payload["status"] == "completed"
    assert payload["already_completed"] is False
    assert payload["replay_path"] == "/session/42"
    assert payload["scoring"]["grade"] == "A"
    assert payload["badges_earned"] == ["clean-ops"]
    assert training_session.status == "completed"
    assert training_session.ended_at is not None


def test_complete_session_is_idempotent_for_completed_sessions(client: TestClient) -> None:
    """Calling completion twice returns success with already_completed=true."""
    local_user_id = uuid.uuid4()
    ended_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    training_session = _make_training_session(
        session_id=11,
        owner_user_id=local_user_id,
        status="completed",
        ended_at=ended_at,
    )

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    mocked_run_scoring = AsyncMock()
    with patch("app.api.v1.sessions._run_scoring", new=mocked_run_scoring):
        response = client.post("/api/v1/sessions/11/complete")

    assert response.status_code == 200
    payload = response.json()
    assert payload["already_completed"] is True
    assert payload["status"] == "completed"
    assert payload["ended_at"] in {ended_at.isoformat(), ended_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert payload["scoring"] is None
    mocked_run_scoring.assert_not_awaited()


def test_complete_session_returns_conflict_for_invalid_status(client: TestClient) -> None:
    """Completion endpoint rejects unsupported status transitions."""
    local_user_id = uuid.uuid4()
    training_session = _make_training_session(
        session_id=7,
        owner_user_id=local_user_id,
        status="draft",
        ended_at=None,
    )

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    response = client.post("/api/v1/sessions/7/complete")

    assert response.status_code == 409
    assert "cannot be completed from status" in response.json()["detail"]


def test_complete_session_returns_404_when_session_missing(client: TestClient) -> None:
    """Completion endpoint returns 404 when session does not exist."""
    _override_auth(uuid.uuid4(), roles=["student"])
    _override_db(None)

    response = client.post("/api/v1/sessions/999/complete")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_complete_session_returns_403_for_non_owner_student(client: TestClient) -> None:
    """Students cannot complete sessions they do not own."""
    local_user_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    training_session = _make_training_session(
        session_id=18,
        owner_user_id=owner_user_id,
        status="active",
        ended_at=None,
    )

    _override_auth(local_user_id, roles=["student"])
    _override_db(training_session)

    response = client.post("/api/v1/sessions/18/complete")

    assert response.status_code == 403
    assert "do not have access" in response.json()["detail"].lower()
