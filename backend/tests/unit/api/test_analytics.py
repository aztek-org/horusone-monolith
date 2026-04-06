"""Unit tests for analytics route query scoping."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import analytics
from app.middleware.auth import TokenUser


class _Result:
    """Simple SQLAlchemy result stub with ``all`` support."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

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


def _build_platform_admin() -> TokenUser:
    return TokenUser(
        keycloak_id="kc-platform-admin",
        email="admin@test.com",
        display_name="Platform Admin",
        roles=["platform-admin"],
        organization_id=None,
    )


@pytest.mark.asyncio
async def test_get_overview_scopes_active_sessions_query_to_org() -> None:
    """Active-session aggregation must remain scoped by org_id and status=active."""
    org_id = uuid.uuid4()
    user = _build_instructor(org_id)
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[40, 25, 6, 12, 18])
    session.execute = AsyncMock(side_effect=[_Result([]), _Result([])])

    with patch.object(analytics, "_validate_org", new=AsyncMock(return_value=None)):
        payload = await analytics.get_overview(user=user, org_id=org_id, session=session)

    assert payload.total_sessions == 40
    assert payload.completed_sessions == 25
    assert payload.active_sessions == 6

    active_query = session.scalar.await_args_list[2].args[0]
    assert active_query.whereclause is not None
    where_clause = str(active_query.whereclause)
    assert "training_sessions.org_id" in where_clause
    assert "training_sessions.status" in where_clause


@pytest.mark.asyncio
async def test_get_leaderboard_scopes_query_to_org() -> None:
    """Leaderboard query must filter by organization scope."""
    org_id = uuid.uuid4()
    user = _build_instructor(org_id)
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_Result(
            [
                SimpleNamespace(
                    user_id=uuid.uuid4(),
                    display_name="Pilot One",
                    email="pilot.one@test.com",
                    completed_sessions=4,
                    total_voice_logs=19,
                    total_duration_ms=210000,
                )
            ]
        )
    )

    with patch.object(analytics, "_validate_org", new=AsyncMock(return_value=None)):
        leaderboard = await analytics.get_leaderboard(
            user=user,
            org_id=org_id,
            limit=5,
            session=session,
        )

    assert len(leaderboard) == 1
    assert leaderboard[0].completed_sessions == 4
    assert leaderboard[0].avg_session_duration_ms == pytest.approx(52500)

    leaderboard_query = session.execute.await_args.args[0]
    assert leaderboard_query.whereclause is not None
    assert "training_sessions.org_id" in str(leaderboard_query.whereclause)


@pytest.mark.asyncio
async def test_platform_org_leaderboard_requires_platform_admin() -> None:
    """Organization leaderboard endpoint is platform-admin only."""
    user = _build_instructor(uuid.uuid4())
    session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await analytics.get_platform_org_leaderboard(_user=user, limit=5, session=session)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_platform_org_leaderboard_returns_ranked_org_rows() -> None:
    """Organization leaderboard should map aggregate rows to response schema."""
    user = _build_platform_admin()
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_Result(
            [
                SimpleNamespace(
                    organization_id=uuid.uuid4(),
                    organization_name="Sky Academy",
                    organization_slug="sky-academy",
                    is_active=True,
                    completed_sessions=20,
                    active_sessions=3,
                    total_sessions=25,
                    active_seats=12,
                ),
                SimpleNamespace(
                    organization_id=uuid.uuid4(),
                    organization_name="Vector Flight",
                    organization_slug="vector-flight",
                    is_active=True,
                    completed_sessions=0,
                    active_sessions=0,
                    total_sessions=0,
                    active_seats=4,
                ),
            ]
        )
    )

    entries = await analytics.get_platform_org_leaderboard(_user=user, limit=5, session=session)

    assert len(entries) == 2
    assert entries[0].organization_name == "Sky Academy"
    assert entries[0].completion_rate == pytest.approx(80.0)
    assert entries[1].organization_slug == "vector-flight"
    assert entries[1].completion_rate == 0.0
