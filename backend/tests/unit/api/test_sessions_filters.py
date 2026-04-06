"""Unit tests for session list filtering behavior."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1 import sessions
from app.middleware.auth import TokenUser


class _Result:
    """Simple SQLAlchemy result stub with scalars().all()."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[object]:
        return self._rows


def _build_instructor(org_id: uuid.UUID) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-instructor",
        email="instructor@test.com",
        display_name="Instructor",
        roles=["instructor"],
        organization_id=str(org_id),
    )


def _build_student(org_id: uuid.UUID) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-student",
        email="student@test.com",
        display_name="Student",
        roles=["student"],
        organization_id=str(org_id),
    )


@pytest.mark.asyncio
async def test_list_sessions_applies_scope_and_filter_clauses() -> None:
    """list_sessions should apply org RBAC scope and optional filter clauses."""
    org_id = uuid.uuid4()
    user = _build_instructor(org_id)
    local_user = SimpleNamespace(id=uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result([]))

    await sessions.list_sessions(
        user=user,
        org_id=org_id,
        local_user=local_user,
        status_filter="completed",
        scenario_id=7,
        started_after=now - timedelta(days=7),
        started_before=now,
        limit=50,
        offset=0,
        session=session,
    )

    query = session.execute.await_args.args[0]
    where_clause = str(query.whereclause)
    assert "training_sessions.org_id" in where_clause
    assert "training_sessions.status" in where_clause
    assert "training_sessions.scenario_id" in where_clause
    assert "training_sessions.started_at" in where_clause


@pytest.mark.asyncio
async def test_list_sessions_rejects_invalid_date_window() -> None:
    """started_after later than started_before should return 400."""
    org_id = uuid.uuid4()
    user = _build_instructor(org_id)
    local_user = SimpleNamespace(id=uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result([]))

    with pytest.raises(HTTPException) as exc_info:
        await sessions.list_sessions(
            user=user,
            org_id=org_id,
            local_user=local_user,
            status_filter=None,
            scenario_id=None,
            started_after=now,
            started_before=now - timedelta(days=1),
            limit=10,
            offset=0,
            session=session,
        )

    assert exc_info.value.status_code == 400
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_sessions_scopes_students_to_own_sessions() -> None:
    """Students should always be scoped to user_id regardless of filters."""
    org_id = uuid.uuid4()
    user = _build_student(org_id)
    local_user = SimpleNamespace(id=uuid.uuid4())
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result([]))

    await sessions.list_sessions(
        user=user,
        org_id=org_id,
        local_user=local_user,
        status_filter="active",
        scenario_id=None,
        started_after=None,
        started_before=None,
        limit=20,
        offset=0,
        session=session,
    )

    query = session.execute.await_args.args[0]
    where_clause = str(query.whereclause)
    assert "training_sessions.user_id" in where_clause
