"""Unit tests for the instructor-profile and student-roster routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import instructors
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.schemas.instructor import InstructorProfileUpdate


def _user(roles: list[str] | None = None, org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles or ["instructor"],
        organization_id=str(org_id) if org_id else None,
    )


class _ScalarsResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarsResult:
        return self

    def all(self) -> list[object]:
        return self._rows


@pytest.mark.asyncio
async def test_get_my_profile_missing_returns_404() -> None:
    with patch.object(
        instructors.instructor_repo,
        "get_profile",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await instructors.get_my_profile(
                user=_user(), local_user=SimpleNamespace(id=uuid.uuid4()), db=object()
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_my_profile_returns_record() -> None:
    profile = SimpleNamespace(id=uuid.uuid4())
    with patch.object(
        instructors.instructor_repo, "get_profile", new=AsyncMock(return_value=profile)
    ):
        result = await instructors.get_my_profile(
            user=_user(), local_user=SimpleNamespace(id=uuid.uuid4()), db=object()
        )

    assert result is profile


@pytest.mark.asyncio
async def test_update_my_profile_sends_only_set_fields() -> None:
    user_id = uuid.uuid4()
    update = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

    with patch.object(
        instructors.instructor_repo, "create_or_update_profile", new=update
    ):
        await instructors.update_my_profile(
            data=InstructorProfileUpdate(bio="CFI since 2010"),
            user=_user(),
            local_user=SimpleNamespace(id=user_id),
            db=object(),
        )

    assert update.await_args.args[1] == user_id
    assert update.await_args.args[2] == {"bio": "CFI since 2010"}


@pytest.mark.asyncio
async def test_get_instructor_profile_missing_returns_404() -> None:
    with patch.object(
        instructors.instructor_repo,
        "get_profile",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as excinfo:
            await instructors.get_instructor_profile(
                user_id=uuid.uuid4(), _user=_user(), db=object()
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_search_instructors_forwards_filters() -> None:
    org_id = uuid.uuid4()
    search = AsyncMock(return_value=[])
    db = object()

    with patch.object(instructors.instructor_repo, "search_instructors", new=search):
        await instructors.search_instructors(
            _user=_user(),
            org_id=org_id,
            specialization="IFR",
            limit=10,
            offset=2,
            db=db,
        )

    assert search.await_args.kwargs == {
        "org_id": org_id,
        "specialization": "IFR",
        "limit": 10,
        "offset": 2,
    }


@pytest.mark.asyncio
async def test_get_my_students_aggregates_roster() -> None:
    org_id = uuid.uuid4()
    student = SimpleNamespace(
        id=uuid.uuid4(), display_name="Pilot One", email="pilot@test.com"
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([student]))
    db.scalar = AsyncMock(side_effect=[2.5, 6, 88.0])

    result = await instructors.get_my_students(
        user=_user(["instructor"], org_id),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        org_id=org_id,
        db=db,
    )

    assert result == [
        {
            "id": str(student.id),
            "user_id": str(student.id),
            "display_name": "Pilot One",
            "email": "pilot@test.com",
            "flight_hours": 2.5,
            "scenarios_completed": 6,
            "overall_score": 88.0,
            "last_active": None,
        }
    ]


@pytest.mark.asyncio
async def test_get_student_detail_not_found_returns_404() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as excinfo:
        await instructors.get_student_detail(
            student_id=uuid.uuid4(),
            user=_user(["instructor"], uuid.uuid4()),
            org_id=uuid.uuid4(),
            db=db,
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_student_detail_without_matching_seat_returns_404() -> None:
    student = SimpleNamespace(
        id=uuid.uuid4(), display_name="Pilot", email="pilot@test.com"
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=student)
    db.scalar = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as excinfo:
        await instructors.get_student_detail(
            student_id=student.id,
            user=_user(["instructor"], uuid.uuid4()),
            org_id=uuid.uuid4(),
            db=db,
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_student_detail_returns_profile_and_sessions() -> None:
    student = SimpleNamespace(
        id=uuid.uuid4(), display_name="Pilot", email="pilot@test.com"
    )
    seat = SimpleNamespace(id=uuid.uuid4())
    recent = SimpleNamespace(
        id=9,
        status="completed",
        started_at=datetime.now(tz=timezone.utc),
        ended_at=None,
        scenario=SimpleNamespace(name="Cross-country"),
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=student)
    db.scalar = AsyncMock(side_effect=[seat, 3.0, 4, 91.0])
    db.execute = AsyncMock(return_value=_ScalarsResult([recent]))

    result = await instructors.get_student_detail(
        student_id=student.id,
        user=_user(["instructor"], uuid.uuid4()),
        org_id=uuid.uuid4(),
        db=db,
    )

    assert result["display_name"] == "Pilot"
    assert result["flight_hours"] == 3.0
    assert result["scenarios_completed"] == 4
    assert result["recent_sessions"][0]["scenario_name"] == "Cross-country"


@pytest.mark.asyncio
async def test_get_my_instructor_stats_returns_aggregates() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[12, 3, 78.4, 5])

    result = await instructors.get_my_instructor_stats(
        user=_user(["instructor"], uuid.uuid4()),
        org_id=uuid.uuid4(),
        db=db,
    )

    assert result == {
        "total_students": 12,
        "active_sessions": 3,
        "average_student_score": 78.4,
        "assessments_created": 5,
    }


@pytest.mark.asyncio
async def test_get_recent_instructor_sessions_maps_rows() -> None:
    ts = SimpleNamespace(
        id=9,
        user=SimpleNamespace(display_name="Pilot"),
        user_id=uuid.uuid4(),
        scenario=SimpleNamespace(name="Approach"),
        status="completed",
        started_at=datetime.now(tz=timezone.utc),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarsResult([ts]))

    result = await instructors.get_recent_instructor_sessions(
        user=_user(["instructor"], uuid.uuid4()),
        org_id=uuid.uuid4(),
        limit=10,
        db=db,
    )

    assert result[0]["student_name"] == "Pilot"
    assert result[0]["scenario_name"] == "Approach"
    assert result[0]["status"] == "completed"


def test_instructor_profile_requires_instructor_role(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(["student"])
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.get("/api/v1/instructors/me/profile")

    assert response.status_code == 403
