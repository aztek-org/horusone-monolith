"""Unit tests for the student statistics routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import stats
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user


def _token(roles: list[str], org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-student",
        email="student@test.com",
        display_name="Student",
        roles=roles,
        organization_id=str(org_id) if org_id else None,
    )


class _ScalarResult:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object | None:
        return self._row


@pytest.mark.asyncio
async def test_get_my_stats_uses_local_user() -> None:
    user_id = uuid.uuid4()
    record = SimpleNamespace(id=uuid.uuid4())
    get_stats = AsyncMock(return_value=record)

    with patch.object(stats.stats_repo, "get_user_stats", new=get_stats):
        result = await stats.get_my_stats(
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            db=object(),
        )

    assert result is record
    assert get_stats.await_args.args[1] == user_id


@pytest.mark.asyncio
async def test_get_my_flight_hours_forwards_pagination() -> None:
    user_id = uuid.uuid4()
    listing = AsyncMock(return_value=[])
    db = object()

    with patch.object(stats.stats_repo, "get_flight_hours", new=listing):
        await stats.get_my_flight_hours(
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            limit=15,
            offset=5,
            db=db,
        )

    assert listing.await_args.args == (db, user_id, 15, 5)


@pytest.mark.asyncio
async def test_get_my_maneuvers_forwards_type_filter() -> None:
    user_id = uuid.uuid4()
    listing = AsyncMock(return_value=[])
    db = object()

    with patch.object(stats.stats_repo, "get_maneuver_logs", new=listing):
        await stats.get_my_maneuvers(
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            maneuver_type="stall",
            limit=20,
            offset=0,
            db=db,
        )

    assert listing.await_args.kwargs["maneuver_type"] == "stall"


@pytest.mark.asyncio
async def test_get_my_assessment_results_uses_assessment_repo() -> None:
    user_id = uuid.uuid4()
    listing = AsyncMock(return_value=[])
    db = object()

    with patch.object(stats.assessment_repo, "get_user_results", new=listing):
        await stats.get_my_assessment_results(
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            limit=20,
            offset=0,
            db=db,
        )

    assert listing.await_args.args == (db, user_id, 20, 0)


@pytest.mark.asyncio
async def test_get_transcript_missing_session_returns_404() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(None))

    with pytest.raises(HTTPException) as excinfo:
        await stats.get_session_transcript(
            session_id=9,
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            db=db,
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_transcript_denies_other_students_session() -> None:
    training_session = SimpleNamespace(id=9, user_id=uuid.uuid4())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(training_session))

    with pytest.raises(HTTPException) as excinfo:
        await stats.get_session_transcript(
            session_id=9,
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            db=db,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_get_transcript_allows_owner() -> None:
    user_id = uuid.uuid4()
    training_session = SimpleNamespace(id=9, user_id=user_id)
    logs = [SimpleNamespace(id=1)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(training_session))

    with patch.object(
        stats.stats_repo, "get_transcript", new=AsyncMock(return_value=logs)
    ):
        result = await stats.get_session_transcript(
            session_id=9,
            user=_token(["student"]),
            _seat=object(),
            local_user=SimpleNamespace(id=user_id),
            db=db,
        )

    assert result == logs


@pytest.mark.asyncio
async def test_get_transcript_allows_instructor_for_other_session() -> None:
    training_session = SimpleNamespace(id=9, user_id=uuid.uuid4())
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(training_session))

    with patch.object(
        stats.stats_repo, "get_transcript", new=AsyncMock(return_value=[])
    ):
        result = await stats.get_session_transcript(
            session_id=9,
            user=_token(["instructor"]),
            _seat=object(),
            local_user=SimpleNamespace(id=uuid.uuid4()),
            db=db,
        )

    assert result == []


@pytest.mark.asyncio
async def test_get_user_stats_forbids_cross_org_instructor() -> None:
    org_id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult(None))

    with pytest.raises(HTTPException) as excinfo:
        await stats.get_user_stats(
            user_id=uuid.uuid4(),
            user=_token(["instructor"], org_id),
            org_id=org_id,
            db=db,
        )

    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_get_user_stats_platform_admin_skips_scope_check() -> None:
    record = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()

    with patch.object(
        stats.stats_repo, "get_user_stats", new=AsyncMock(return_value=record)
    ):
        result = await stats.get_user_stats(
            user_id=uuid.uuid4(),
            user=_token(["platform-admin"]),
            org_id=None,
            db=db,
        )

    assert result is record
    db.execute.assert_not_awaited()


def test_get_user_stats_requires_instructor_role(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _token(["student"])
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.get(f"/api/v1/stats/{uuid.uuid4()}")

    assert response.status_code == 403
