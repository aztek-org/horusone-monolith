"""Unit tests for the flight-plan schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.flight_plan import (
    FlightPlanCreate,
    FlightPlanFromImage,
    FlightPlanFromText,
    FlightPlanLegCreate,
    FlightPlanRead,
    FlightPlanUpdate,
    ValidationResponse,
    ValidationResult,
)


def _valid_create(**overrides):
    payload = {
        "title": "KJFK to KBOS",
        "departure_icao": "KJFK",
        "arrival_icao": "KBOS",
    }
    payload.update(overrides)
    return FlightPlanCreate(**payload)


class TestFlightPlanCreate:
    def test_defaults(self) -> None:
        plan = _valid_create()
        assert plan.source_type == "form"
        assert plan.status == "draft"
        assert plan.weather_briefing == {}
        assert plan.airspace_restrictions == []
        assert plan.alternate_icao is None

    def test_title_is_required(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            FlightPlanCreate(departure_icao="KJFK", arrival_icao="KBOS")

    def test_icao_must_be_uppercase_alnum(self) -> None:
        with pytest.raises(ValidationError, match="departure_icao"):
            _valid_create(departure_icao="kjfk")

    def test_icao_rejects_too_short_value(self) -> None:
        with pytest.raises(ValidationError, match="departure_icao"):
            _valid_create(departure_icao="KJ")

    def test_alternate_is_optional(self) -> None:
        plan = _valid_create(alternate_icao="KORD")
        assert plan.alternate_icao == "KORD"

    def test_rejects_invalid_source_type(self) -> None:
        with pytest.raises(ValidationError, match="source_type"):
            _valid_create(source_type="carrier-pigeon")

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValidationError, match="status"):
            _valid_create(status="wip")

    def test_rejects_negative_fuel(self) -> None:
        with pytest.raises(ValidationError, match="fuel_required_gal"):
            _valid_create(fuel_required_gal=-1)


class TestFlightPlanUpdate:
    def test_all_fields_optional(self) -> None:
        update = FlightPlanUpdate()
        assert update.title is None
        assert update.status is None

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValidationError, match="status"):
            FlightPlanUpdate(status="flying")


class TestFlightPlanLegCreate:
    def test_valid_leg(self) -> None:
        leg = FlightPlanLegCreate(sequence=0, from_identifier="KJFK", to_identifier="KBOS")
        assert leg.sequence == 0
        assert leg.distance_nm is None

    def test_rejects_negative_sequence(self) -> None:
        with pytest.raises(ValidationError, match="sequence"):
            FlightPlanLegCreate(sequence=-1)

    def test_rejects_heading_over_360(self) -> None:
        with pytest.raises(ValidationError, match="magnetic_heading"):
            FlightPlanLegCreate(sequence=0, magnetic_heading=361)

    def test_rejects_negative_distance(self) -> None:
        with pytest.raises(ValidationError, match="distance_nm"):
            FlightPlanLegCreate(sequence=0, distance_nm=-0.1)


class TestSpecialInputs:
    def test_from_text_requires_minimum_length(self) -> None:
        with pytest.raises(ValidationError, match="text"):
            FlightPlanFromText(text="too short")

    def test_from_text_accepts_description(self) -> None:
        payload = FlightPlanFromText(text="VFR from KJFK to KBOS at 5500")
        assert payload.title is None

    def test_from_image_requires_long_base64(self) -> None:
        with pytest.raises(ValidationError, match="image_base64"):
            FlightPlanFromImage(image_base64="abc")

    def test_from_image_accepts_long_payload(self) -> None:
        assert FlightPlanFromImage(image_base64="a" * 100).title is None


class TestFlightPlanRead:
    def test_requires_server_fields(self) -> None:
        with pytest.raises(ValidationError):
            FlightPlanRead(title="x", departure_icao="KJFK", arrival_icao="KBOS")

    def test_defaults_legs_empty(self) -> None:
        read = FlightPlanRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            title="x",
            departure_icao="KJFK",
            arrival_icao="KBOS",
            weather_briefing={},
            airspace_restrictions=[],
            source_type="form",
            status="draft",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert read.legs == []


class TestValidationResponse:
    def test_defaults(self) -> None:
        result = ValidationResult(agent="weather", message="ok")
        assert result.passed is False
        assert result.severity == "info"

    def test_response_defaults(self) -> None:
        response = ValidationResponse(plan_id="p1", valid=True)
        assert response.results == []
        assert response.weather is None
        assert response.session_id is None
