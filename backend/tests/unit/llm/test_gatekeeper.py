"""Unit tests for the deterministic gatekeeper flight-plan validator."""

from __future__ import annotations

from typing import Any

from app.services.llm.agents.gatekeeper import validate_flight_plan
from app.services.llm.state import SessionPhase, Severity


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "departure_icao": "KLAX",
        "arrival_icao": "KSFO",
        "route": [
            {"name": "KLAX", "lat": 33.94, "lng": -118.40},
            {"name": "KSFO", "lat": 37.62, "lng": -122.38},
        ],
        "fuel_on_board": 30.0,
        "fuel_reserve": 5.0,
        "total_weight": 2000.0,
        "max_weight": 2450.0,
        "flight_rules": "VFR",
    }
    plan.update(overrides)
    return plan


def _gatekeeper_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in result["validation_results"] if r["agent"] == "gatekeeper"]


def test_missing_flight_plan_is_a_critical_failure() -> None:
    result = validate_flight_plan({})

    gate = _gatekeeper_results(result)
    assert len(gate) == 1
    assert gate[0]["passed"] is False
    assert gate[0]["severity"] == Severity.CRITICAL.value
    assert result["validation_passed"] is False
    assert result["phase"] == SessionPhase.VALIDATION.value


def test_valid_plan_records_a_success_result() -> None:
    result = validate_flight_plan({"flight_plan": _plan()})

    gate = _gatekeeper_results(result)
    assert len(gate) == 1
    assert gate[0]["passed"] is True
    assert gate[0]["severity"] == Severity.INFO.value
    assert "validated successfully" in gate[0]["message"]
    assert "validation_passed" not in result
    assert result["phase"] == SessionPhase.VALIDATION.value


def test_missing_departure_or_arrival_is_critical() -> None:
    result = validate_flight_plan({"flight_plan": _plan(arrival_icao="")})

    critical = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.CRITICAL.value]
    assert any("ICAO code missing" in r["message"] for r in critical)


def test_route_with_fewer_than_two_waypoints_is_critical() -> None:
    result = validate_flight_plan({"flight_plan": _plan(route=[{"name": "KLAX"}])})

    critical = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.CRITICAL.value]
    assert any("at least 2 waypoints" in r["message"] for r in critical)


def test_waypoint_names_must_match_departure_and_arrival() -> None:
    result = validate_flight_plan(
        {
            "flight_plan": _plan(
                route=[
                    {"name": "WRONG", "lat": 1.0, "lng": 1.0},
                    {"name": "ALSO-WRONG", "lat": 2.0, "lng": 2.0},
                ]
            )
        }
    )

    warnings = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.WARNING.value]
    assert any("does not match departure" in r["message"] for r in warnings)
    assert any("does not match arrival" in r["message"] for r in warnings)


def test_waypoints_without_coordinates_are_flagged() -> None:
    result = validate_flight_plan(
        {
            "flight_plan": _plan(
                route=[{"name": "KLAX"}, {"name": "KSFO"}]
            )
        }
    )

    warnings = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.WARNING.value]
    assert sum("missing coordinates" in r["message"] for r in warnings) == 2


def test_identifier_is_used_when_name_is_absent() -> None:
    result = validate_flight_plan(
        {
            "flight_plan": _plan(
                route=[
                    {"identifier": "KLAX", "lat": 33.94, "lng": -118.40},
                    {"identifier": "KSFO", "lat": 37.62, "lng": -122.38},
                ]
            )
        }
    )

    gate = _gatekeeper_results(result)
    assert gate[0]["passed"] is True


def test_zero_fuel_on_board_is_critical() -> None:
    result = validate_flight_plan({"flight_plan": _plan(fuel_on_board=0.0)})

    critical = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.CRITICAL.value]
    assert any("Fuel on board must be greater than zero" in r["message"] for r in critical)


def test_zero_fuel_reserve_is_a_warning() -> None:
    result = validate_flight_plan({"flight_plan": _plan(fuel_reserve=0.0)})

    warnings = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.WARNING.value]
    assert any("reserve is zero or negative" in r["message"] for r in warnings)


def test_overweight_aircraft_is_critical() -> None:
    result = validate_flight_plan(
        {"flight_plan": _plan(total_weight=3000.0, max_weight=2450.0)}
    )

    critical = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.CRITICAL.value]
    assert any("overweight" in r["message"] for r in critical)


def test_ifr_without_alternate_is_a_warning() -> None:
    result = validate_flight_plan({"flight_plan": _plan(flight_rules="IFR")})

    warnings = [r for r in _gatekeeper_results(result) if r["severity"] == Severity.WARNING.value]
    assert any("without an alternate" in r["message"] for r in warnings)


def test_ifr_with_alternate_passes() -> None:
    result = validate_flight_plan(
        {"flight_plan": _plan(flight_rules="IFR", alternate_icao="KOAK")}
    )

    assert _gatekeeper_results(result)[0]["passed"] is True


def test_existing_validation_results_are_preserved() -> None:
    existing = {
        "agent": "prior",
        "passed": True,
        "severity": Severity.INFO.value,
        "message": "prior",
        "details": None,
    }

    result = validate_flight_plan(
        {"flight_plan": _plan(), "validation_results": [existing]}
    )

    assert result["validation_results"][0] == existing
    assert len(result["validation_results"]) == 2
