"""Unit tests for the student-statistics schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.student_stats import (
    FlightHourLogCreate,
    FlightHourLogRead,
    ManeuverLogCreate,
    ManeuverLogRead,
    StudentStatsRead,
)


class TestFlightHourLogCreate:
    def test_valid_entry(self) -> None:
        log = FlightHourLogCreate(hours_logged=1.5, phase="enroute")
        assert log.hours_logged == 1.5
        assert log.maneuvers_practiced == []
        assert log.session_id is None

    def test_hours_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="hours_logged"):
            FlightHourLogCreate(hours_logged=0, phase="ground")

    @pytest.mark.parametrize(
        "phase", ["ground", "departure", "enroute", "approach", "landing"]
    )
    def test_accepts_supported_phases(self, phase: str) -> None:
        assert FlightHourLogCreate(hours_logged=1, phase=phase).phase == phase

    def test_rejects_unsupported_phase(self) -> None:
        with pytest.raises(ValidationError, match="phase"):
            FlightHourLogCreate(hours_logged=1, phase="cruise")


class TestManeuverLogCreate:
    def test_defaults(self) -> None:
        log = ManeuverLogCreate(maneuver_name="Steep Turn", maneuver_type="turn")
        assert log.score is None
        assert log.duration_seconds is None
        assert log.extra_data == {}

    def test_requires_maneuver_name(self) -> None:
        with pytest.raises(ValidationError, match="maneuver_name"):
            ManeuverLogCreate(maneuver_name="", maneuver_type="turn")

    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError, match="score"):
            ManeuverLogCreate(maneuver_name="S", maneuver_type="t", score=101)

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(ValidationError, match="duration_seconds"):
            ManeuverLogCreate(maneuver_name="S", maneuver_type="t", duration_seconds=-1)


class TestStudentStatsRead:
    def test_accepts_full_row(self) -> None:
        stats = StudentStatsRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            total_flight_hours=12.5,
            total_maneuvers=30,
            total_scenarios_completed=8,
            total_assessments=2,
            overall_score=88.0,
            current_streak=3,
            best_streak=7,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
        )
        assert stats.best_streak == 7


class TestReadModels:
    def test_flight_hour_log_read_defaults(self) -> None:
        log = FlightHourLogRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            hours_logged=1.0,
            maneuvers_practiced=[],
            phase="ground",
            created_at="2024-01-01T00:00:00",
        )
        assert log.session_id is None
        assert log.notes is None

    def test_maneuver_log_read_defaults(self) -> None:
        log = ManeuverLogRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            maneuver_name="S",
            maneuver_type="t",
            extra_data={},
            created_at="2024-01-01T00:00:00",
        )
        assert log.score is None
