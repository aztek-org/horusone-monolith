"""Unit tests for WaypointRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.waypoint_repository import WaypointRepository, _haversine_nm
from app.models.waypoint import FlightInsight, ScenarioWaypoint, SessionTrack, Waypoint


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── Pure helper ────────────────────────────────────────────────────────


class TestHaversine:
    """Tests for the great-circle distance helper."""

    def test_same_point_is_zero(self) -> None:
        assert _haversine_nm(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_known_distance_is_reasonable(self) -> None:
        # 1 degree of latitude is ~60 NM.
        distance = _haversine_nm(0.0, 0.0, 1.0, 0.0)
        assert 59.0 < distance < 61.0


# ── WaypointRepository ─────────────────────────────────────────────────


class TestWaypointRepository:
    """Tests for waypoint, track, and insight queries."""

    @pytest.mark.asyncio
    async def test_search_waypoints_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = WaypointRepository()

        assert await repo.search_waypoints(session) == rows

    @pytest.mark.asyncio
    async def test_search_waypoints_type_filter(self) -> None:
        session = _mock_session_scalars([])
        repo = WaypointRepository()

        await repo.search_waypoints(session, wp_type="VOR")

        query = str(session.execute.await_args.args[0])
        assert "waypoints.type" in query

    @pytest.mark.asyncio
    async def test_search_waypoints_proximity_post_filter(self) -> None:
        near = MagicMock()
        near.lat = 0.0
        near.lng = 0.0
        far = MagicMock()
        far.lat = 10.0
        far.lng = 10.0
        session = _mock_session_scalars([near, far])
        repo = WaypointRepository()

        result = await repo.search_waypoints(
            session, near_lat=0.0, near_lng=0.0, radius_nm=50.0
        )

        assert result == [near]

    @pytest.mark.asyncio
    async def test_search_waypoints_limit_applied_after_filter(self) -> None:
        points = []
        for index in range(5):
            wp = MagicMock()
            wp.lat = 0.0
            wp.lng = 0.0
            points.append(wp)
        session = _mock_session_scalars(points)
        repo = WaypointRepository()

        result = await repo.search_waypoints(
            session, near_lat=0.0, near_lng=0.0, radius_nm=50.0, limit=2
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_waypoint_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = WaypointRepository()

        assert await repo.get_waypoint(session, uuid.uuid4()) is fake

    @pytest.mark.asyncio
    async def test_get_waypoint_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = WaypointRepository()

        assert await repo.get_waypoint(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_create_waypoint_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = WaypointRepository()

        result = await repo.create_waypoint(
            session,
            {"name": "JFK", "type": "airport", "lat": 40.6, "lng": -73.7},
        )

        assert isinstance(result, Waypoint)
        assert result.name == "JFK"
        assert result.lat == 40.6
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_scenario_waypoints_returns_rows(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = WaypointRepository()

        result = await repo.get_scenario_waypoints(session, 3)

        assert result == rows
        query = str(session.execute.await_args.args[0])
        assert "scenario_waypoints.scenario_id" in query

    @pytest.mark.asyncio
    async def test_add_scenario_waypoint_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = WaypointRepository()
        waypoint_id = uuid.uuid4()

        result = await repo.add_scenario_waypoint(
            session,
            scenario_id=3,
            waypoint_id=waypoint_id,
            sequence=2,
            altitude_constraint="3000ft",
            notes="hold short",
        )

        assert isinstance(result, ScenarioWaypoint)
        assert result.scenario_id == 3
        assert result.waypoint_id == waypoint_id
        assert result.sequence_order == 2
        assert result.altitude_constraint == "3000ft"
        session.add.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_get_session_track_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = WaypointRepository()

        assert await repo.get_session_track(session, 9) is fake

    @pytest.mark.asyncio
    async def test_get_session_track_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = WaypointRepository()

        assert await repo.get_session_track(session, 9) is None

    @pytest.mark.asyncio
    async def test_save_session_track_updates_existing(self) -> None:
        existing = MagicMock()
        session = _mock_session(scalar_result=existing)
        repo = WaypointRepository()
        points = [{"lat": 1.0, "lng": 2.0}]

        result = await repo.save_session_track(session, 9, points, total_distance=12.5)

        assert result is existing
        assert existing.track_points == points
        assert existing.total_distance_nm == 12.5
        session.add.assert_not_called()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_session_track_creates_new(self) -> None:
        session = _mock_session(scalar_result=None)
        session.add = MagicMock()
        repo = WaypointRepository()

        result = await repo.save_session_track(session, 9, [{"lat": 1.0}], total_distance=3.0)

        assert isinstance(result, SessionTrack)
        assert result.session_id == 9
        assert result.total_distance_nm == 3.0
        session.add.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_get_flight_insights_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = WaypointRepository()

        assert await repo.get_flight_insights(session, 9) == rows

    @pytest.mark.asyncio
    async def test_create_flight_insight_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = WaypointRepository()

        result = await repo.create_flight_insight(
            session,
            {
                "session_id": 9,
                "type": "deviation",
                "severity": "minor",
                "title": "Heading deviation",
                "description": "Drifted 10 degrees off course",
                "timestamp_in_session": 42.0,
            },
        )

        assert isinstance(result, FlightInsight)
        assert result.session_id == 9
        assert result.severity == "minor"
        session.add.assert_called_once_with(result)
