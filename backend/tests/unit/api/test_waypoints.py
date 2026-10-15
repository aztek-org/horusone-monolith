"""Unit tests for the waypoint, track, and insight routes."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import waypoints
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import require_active_seat
from app.schemas.waypoint import ScenarioWaypointCreate, WaypointCreate


def _user() -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=["instructor"],
        organization_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_search_waypoints_forwards_filters() -> None:
    repo_search = AsyncMock(return_value=[SimpleNamespace(id=uuid.uuid4())])
    db = object()

    with patch.object(waypoints.waypoint_repo, "search_waypoints", new=repo_search):
        result = await waypoints.search_waypoints(
            _user=_user(),
            type="airport",
            near_lat=34.0,
            near_lng=-118.0,
            radius=25.0,
            limit=5,
            db=db,
        )

    assert len(result) == 1
    assert repo_search.await_args.kwargs == {
        "wp_type": "airport",
        "near_lat": 34.0,
        "near_lng": -118.0,
        "radius_nm": 25.0,
        "limit": 5,
    }


@pytest.mark.asyncio
async def test_create_waypoint_persists_payload() -> None:
    db = object()
    create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    data = WaypointCreate(name="DAG", type="VOR", lat=34.9, lng=-116.8)

    with patch.object(waypoints.waypoint_repo, "create_waypoint", new=create):
        await waypoints.create_waypoint(data=data, _user=_user(), _seat=object(), db=db)

    assert create.await_args.args == (db, data.model_dump())


@pytest.mark.asyncio
async def test_get_scenario_waypoints_forwards_scenario_id() -> None:
    db = object()
    listing = AsyncMock(return_value=[])
    with patch.object(
        waypoints.waypoint_repo, "get_scenario_waypoints", new=listing
    ):
        await waypoints.get_scenario_waypoints(
            scenario_id=42, _user=_user(), db=db
        )

    assert listing.await_args.args == (db, 42)


@pytest.mark.asyncio
async def test_add_scenario_waypoint_forwards_constraints() -> None:
    db = object()
    waypoint_id = uuid.uuid4()
    add = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    data = ScenarioWaypointCreate(
        waypoint_id=waypoint_id,
        sequence_order=2,
        altitude_constraint="FL100",
        speed_constraint="180",
        notes="turn right",
    )

    with patch.object(waypoints.waypoint_repo, "add_scenario_waypoint", new=add):
        await waypoints.add_scenario_waypoint(
            scenario_id=3, data=data, _user=_user(), _seat=object(), db=db
        )

    assert add.await_args.kwargs == {
        "scenario_id": 3,
        "waypoint_id": waypoint_id,
        "sequence": 2,
        "altitude_constraint": "FL100",
        "speed_constraint": "180",
        "notes": "turn right",
    }


@pytest.mark.asyncio
async def test_get_session_track_missing_returns_404() -> None:
    with patch.object(
        waypoints.waypoint_repo, "get_session_track", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(HTTPException) as excinfo:
            await waypoints.get_session_track(
                session_id=9, _user=_user(), _seat=object(), db=object()
            )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_session_track_returns_record() -> None:
    track = SimpleNamespace(id=uuid.uuid4())
    with patch.object(
        waypoints.waypoint_repo, "get_session_track", new=AsyncMock(return_value=track)
    ):
        result = await waypoints.get_session_track(
            session_id=9, _user=_user(), _seat=object(), db=object()
        )

    assert result is track


@pytest.mark.asyncio
async def test_get_session_insights_returns_list() -> None:
    insights = [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]
    with patch.object(
        waypoints.waypoint_repo,
        "get_flight_insights",
        new=AsyncMock(return_value=insights),
    ):
        result = await waypoints.get_session_insights(
            session_id=9, _user=_user(), _seat=object(), db=object()
        )

    assert result == insights


def test_create_waypoint_requires_instructor_role(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: TokenUser(
        keycloak_id="kc-student",
        email="student@test.com",
        display_name="Student",
        roles=["student"],
    )
    app.dependency_overrides[require_active_seat] = lambda: object()
    app.dependency_overrides[get_db_session] = lambda: object()

    response = client.post(
        "/api/v1/waypoints/",
        json={"name": "DAG", "type": "VOR", "lat": 34.9, "lng": -116.8},
    )

    assert response.status_code == 403
