"""Unit tests for the waypoint / track / insight schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.waypoint import (
    FlightInsightRead,
    ScenarioWaypointCreate,
    ScenarioWaypointRead,
    SessionTrackRead,
    WaypointCreate,
    WaypointRead,
)


class TestWaypointCreate:
    def test_defaults(self) -> None:
        wp = WaypointCreate(name="MERIT", type="fix", lat=40.0, lng=-73.0)
        assert wp.extra_data == {}
        assert wp.identifier is None
        assert wp.elevation_ft is None

    @pytest.mark.parametrize(
        "type_", ["waypoint", "airport", "VOR", "NDB", "fix", "intersection"]
    )
    def test_accepts_supported_types(self, type_: str) -> None:
        wp = WaypointCreate(name="X", type=type_, lat=0.0, lng=0.0)
        assert wp.type == type_

    def test_rejects_unsupported_type(self) -> None:
        with pytest.raises(ValidationError, match="type"):
            WaypointCreate(name="X", type="helipad", lat=0.0, lng=0.0)

    def test_rejects_out_of_range_latitude(self) -> None:
        with pytest.raises(ValidationError, match="lat"):
            WaypointCreate(name="X", type="fix", lat=91.0, lng=0.0)

    def test_rejects_out_of_range_longitude(self) -> None:
        with pytest.raises(ValidationError, match="lng"):
            WaypointCreate(name="X", type="fix", lat=0.0, lng=181.0)


class TestWaypointRead:
    def test_requires_server_fields(self) -> None:
        with pytest.raises(ValidationError):
            WaypointRead(name="X", type="fix", lat=0.0, lng=0.0)

    def test_accepts_full_row(self) -> None:
        read = WaypointRead(
            id=uuid.uuid4(),
            name="MERIT",
            type="fix",
            lat=40.0,
            lng=-73.0,
            extra_data={},
            created_at="2024-01-01T00:00:00",
        )
        assert read.identifier is None


class TestScenarioWaypoint:
    def test_create_requires_waypoint_and_sequence(self) -> None:
        with pytest.raises(ValidationError, match="waypoint_id"):
            ScenarioWaypointCreate(sequence_order=0)

    def test_rejects_negative_sequence(self) -> None:
        with pytest.raises(ValidationError, match="sequence_order"):
            ScenarioWaypointCreate(waypoint_id=uuid.uuid4(), sequence_order=-1)

    def test_create_defaults(self) -> None:
        link = ScenarioWaypointCreate(waypoint_id=uuid.uuid4(), sequence_order=2)
        assert link.altitude_constraint is None
        assert link.notes is None

    def test_read_requires_server_ids(self) -> None:
        read = ScenarioWaypointRead(
            id=uuid.uuid4(),
            scenario_id=1,
            waypoint_id=uuid.uuid4(),
            sequence_order=1,
        )
        assert read.speed_constraint is None


class TestSessionTrackRead:
    def test_accepts_track_points(self) -> None:
        track = SessionTrackRead(
            id=uuid.uuid4(),
            session_id=1,
            track_points=[{"lat": 1.0}],
            recorded_at="2024-01-01T00:00:00",
        )
        assert track.total_distance_nm is None
        assert len(track.track_points) == 1


class TestFlightInsightRead:
    def test_accepts_full_row(self) -> None:
        insight = FlightInsightRead(
            id=uuid.uuid4(),
            session_id=1,
            type="safety",
            severity="warning",
            title="Low altitude",
            description="desc",
            timestamp_in_session=12.5,
            extra_data={},
            created_at="2024-01-01T00:00:00",
        )
        assert insight.timestamp_in_session == 12.5
