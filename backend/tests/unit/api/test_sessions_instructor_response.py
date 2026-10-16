"""Unit tests for the HITL instructor-response route.

The route is the only caller of ``TrainingSessionModule.await_instructor``, so
these tests pin both the authorization contract (active seat + instructor seat
role + tenant scoping) and the release/idempotency behaviour a held exchange
depends on.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1 import sessions
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import get_authenticated_user, require_active_seat
from app.models.training_session import TrainingSession
from app.schemas.training_session import InstructorResponseRequest
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from tests.conftest import FakeSessionModule


class _SessionResult:
    """SQLAlchemy result stub with ``scalar_one_or_none`` support."""

    def __init__(self, training_session: object | None) -> None:
        self._training_session = training_session

    def scalar_one_or_none(self) -> object | None:
        return self._training_session


def _fake_request(session_module: FakeSessionModule) -> SimpleNamespace:
    """Stand in for a request whose app has the composition root installed."""
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                session_module=session_module,
                scene_registry=SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE}),
                settings=SimpleNamespace(environment="testing"),
            )
        )
    )


def _training_session(session_id: int, org_id: uuid.UUID | None) -> TrainingSession:
    return TrainingSession(
        id=session_id,
        user_id=uuid.uuid4(),
        org_id=org_id,
        status="active",
        scene_version=DEFAULT_SCENE.version,
        language="en",
        started_at=datetime.now(tz=timezone.utc),
    )


def _instructor(org_id: uuid.UUID | None, *, roles: list[str] | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-instructor",
        email="instructor@test.com",
        display_name="Instructor",
        roles=roles or ["instructor"],
        organization_id=str(org_id) if org_id else None,
    )


def _db_returning(training_session: TrainingSession | None) -> object:
    class _StubDb:
        async def execute(self, *_args: object, **_kwargs: object) -> _SessionResult:
            return _SessionResult(training_session)

    return _StubDb()


@pytest.mark.asyncio
async def test_instructor_override_releases_held_exchange() -> None:
    """An instructor seat releases the pending exchange with supplied text."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True)

    response = await sessions.submit_instructor_response(
        session_id=42,
        data=InstructorResponseRequest(instructor_response="Cleared for takeoff, wind 270."),
        request=_fake_request(session_module),
        user=_instructor(org_id),
        seat=SimpleNamespace(role="instructor"),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        session=_db_returning(_training_session(42, org_id)),
    )

    assert response.applied is True
    assert response.instructor_overridden is True
    assert response.pending_instructor is False
    assert response.atc_response == "Cleared for takeoff, wind 270."

    assert len(session_module.awaited) == 1
    awaited = session_module.awaited[0]
    assert awaited.org_id == org_id
    assert awaited.session_id == 42
    assert awaited.instructor_response == "Cleared for takeoff, wind 270."


@pytest.mark.asyncio
async def test_release_without_override_uses_graph_response() -> None:
    """No override text releases the graph's own response, unmodified."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True, atc_response="Graph says hold.")

    response = await sessions.submit_instructor_response(
        session_id=7,
        data=InstructorResponseRequest(),
        request=_fake_request(session_module),
        user=_instructor(org_id),
        seat=SimpleNamespace(role="instructor"),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        session=_db_returning(_training_session(7, org_id)),
    )

    assert response.applied is True
    assert response.instructor_overridden is False
    assert response.atc_response == "Graph says hold."
    assert session_module.awaited[0].instructor_response is None


@pytest.mark.asyncio
async def test_student_seat_is_forbidden() -> None:
    """A student seat may not release an exchange, even in their own org."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True)

    with pytest.raises(HTTPException) as excinfo:
        await sessions.submit_instructor_response(
            session_id=9,
            data=InstructorResponseRequest(instructor_response="let me in"),
            request=_fake_request(session_module),
            user=_instructor(org_id, roles=["student"]),
            seat=SimpleNamespace(role="student"),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            session=_db_returning(_training_session(9, org_id)),
        )

    assert excinfo.value.status_code == 403
    assert session_module.awaited == []


@pytest.mark.asyncio
async def test_cross_tenant_instructor_is_forbidden() -> None:
    """An instructor seat cannot release another tenant's session."""
    session_module = FakeSessionModule(pending_instructor=True)

    with pytest.raises(HTTPException) as excinfo:
        await sessions.submit_instructor_response(
            session_id=11,
            data=InstructorResponseRequest(instructor_response="cleared"),
            request=_fake_request(session_module),
            user=_instructor(uuid.uuid4()),
            seat=SimpleNamespace(role="instructor"),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            session=_db_returning(_training_session(11, uuid.uuid4())),
        )

    assert excinfo.value.status_code == 403
    assert session_module.awaited == []


@pytest.mark.asyncio
async def test_org_admin_seat_can_review() -> None:
    """Admin seats are instructor-capable, matching the instructor roster rule."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True)

    response = await sessions.submit_instructor_response(
        session_id=13,
        data=InstructorResponseRequest(instructor_response="cleared"),
        request=_fake_request(session_module),
        user=_instructor(org_id, roles=["org-admin"]),
        seat=SimpleNamespace(role="admin"),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        session=_db_returning(_training_session(13, org_id)),
    )

    assert response.applied is True


@pytest.mark.asyncio
async def test_platform_admin_reviews_without_matching_org() -> None:
    """Platform admins bypass both the seat role and the tenant comparison."""
    session_module = FakeSessionModule(pending_instructor=True)

    response = await sessions.submit_instructor_response(
        session_id=15,
        data=InstructorResponseRequest(instructor_response="cleared"),
        request=_fake_request(session_module),
        user=_instructor(None, roles=["platform-admin"]),
        seat=SimpleNamespace(role="admin"),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        session=_db_returning(_training_session(15, uuid.uuid4())),
    )

    assert response.applied is True
    assert len(session_module.awaited) == 1


@pytest.mark.asyncio
async def test_no_pending_exchange_is_idempotent() -> None:
    """Releasing with nothing pending is a successful no-op, not an error."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=False)

    response = await sessions.submit_instructor_response(
        session_id=3,
        data=InstructorResponseRequest(instructor_response="nothing held"),
        request=_fake_request(session_module),
        user=_instructor(org_id),
        seat=SimpleNamespace(role="instructor"),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        session=_db_returning(_training_session(3, org_id)),
    )

    assert response.applied is False
    assert response.pending_instructor is False
    assert len(session_module.awaited) == 1


@pytest.mark.asyncio
async def test_missing_session_is_not_found() -> None:
    """An unknown session id is a 404, before any module call."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True)

    with pytest.raises(HTTPException) as excinfo:
        await sessions.submit_instructor_response(
            session_id=999,
            data=InstructorResponseRequest(instructor_response="cleared"),
            request=_fake_request(session_module),
            user=_instructor(org_id),
            seat=SimpleNamespace(role="instructor"),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            session=_db_returning(None),
        )

    assert excinfo.value.status_code == 404
    assert session_module.awaited == []


def test_blank_override_is_rejected() -> None:
    """Whitespace-only override text is not a release."""
    with pytest.raises(ValidationError):
        InstructorResponseRequest(instructor_response="   ")


def _override_http(*, role: str, org_id: uuid.UUID | None, roles: list[str]) -> None:
    token_user = _instructor(org_id, roles=roles)
    app.dependency_overrides[get_current_user] = lambda: token_user
    app.dependency_overrides[require_active_seat] = lambda: SimpleNamespace(role=role)
    app.dependency_overrides[get_authenticated_user] = lambda: SimpleNamespace(id=uuid.uuid4())


def test_http_instructor_release_succeeds(client: TestClient) -> None:
    """Over HTTP, an instructor seat reaches the module and gets a payload back."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True, atc_response="cleared")
    client.app.state.session_module = session_module
    _override_http(role="instructor", org_id=org_id, roles=["instructor"])
    app.dependency_overrides[get_db_session] = lambda: _db_returning(_training_session(5, org_id))

    response = client.post(
        "/api/v1/sessions/5/instructor-response",
        json={"instructor_response": "cleared"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] is True
    assert response.json()["instructor_overridden"] is True
    assert session_module.awaited[0].session_id == 5


def test_http_student_seat_is_forbidden(client: TestClient) -> None:
    """Over HTTP, a student seat is refused and the module is never called."""
    org_id = uuid.uuid4()
    session_module = FakeSessionModule(pending_instructor=True)
    client.app.state.session_module = session_module
    _override_http(role="student", org_id=org_id, roles=["student"])
    app.dependency_overrides[get_db_session] = lambda: _db_returning(_training_session(6, org_id))

    response = client.post(
        "/api/v1/sessions/6/instructor-response",
        json={"instructor_response": "cleared"},
    )

    assert response.status_code == 403, response.text
    assert session_module.awaited == []
