"""Unit tests for the deterministic fuel-calculation agent."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.agents.fuel_agent import calculate_fuel
from app.services.llm.state import Severity

# (0,0) → (0,1) is ~60.04 NM.
ROUTE = [
    {"name": "KAAA", "lat": 0.0, "lng": 0.0},
    {"name": "KBBB", "lat": 0.0, "lng": 1.0},
]


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "route": ROUTE,
        "aircraft_type": "C172",
        "fuel_on_board": 30.0,
        "flight_rules": "VFR",
        "cruise_altitude": 5000,
    }
    plan.update(overrides)
    return plan


def _fuel_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in result["validation_results"] if r["agent"] == "fuel"]


def test_sufficient_fuel_computes_real_burn_and_reserve() -> None:
    result = calculate_fuel({"flight_plan": _plan()})

    fuel = result["fuel_state"]
    # 60.04 NM at 110 kts with 8.33 gph ≈ 4.55 gal.
    assert fuel["total_burn"] == pytest.approx(4.55, abs=0.02)
    assert fuel["reserve_required"] == pytest.approx(6.38)
    assert fuel["reserve_available"] == pytest.approx(25.45, abs=0.02)
    assert fuel["sufficient"] is True
    assert len(fuel["legs"]) == 1
    assert fuel["legs"][0]["leg"] == 1
    assert fuel["legs"][0]["from"] == "KAAA"
    assert fuel["legs"][0]["to"] == "KBBB"
    assert fuel["legs"][0]["distance_nm"] == pytest.approx(60.0, abs=0.2)
    assert fuel["legs"][0]["altitude_ft"] == 5000
    assert fuel["legs"][0]["fuel_burn_gal"] == pytest.approx(4.55, abs=0.02)
    assert "SUFFICIENT" in fuel["message"]


def test_insufficient_fuel_marks_the_result_critical() -> None:
    result = calculate_fuel({"flight_plan": _plan(fuel_on_board=5.0)})

    assert result["fuel_state"]["sufficient"] is False
    results = _fuel_results(result)
    assert results[0]["passed"] is False
    assert results[0]["severity"] == Severity.CRITICAL.value
    assert "Insufficient fuel" in results[0]["message"]


def test_empty_route_produces_no_legs_and_zero_burn() -> None:
    result = calculate_fuel({"flight_plan": _plan(route=[], fuel_on_board=10.0)})

    assert result["fuel_state"]["legs"] == []
    assert result["fuel_state"]["total_burn"] == 0.0
    assert result["fuel_state"]["sufficient"] is True


def test_flight_level_altitude_string_is_converted_to_feet() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0, "altitude": "FL050"},
    ]

    result = calculate_fuel({"flight_plan": _plan(route=route)})

    assert result["fuel_state"]["legs"][0]["altitude_ft"] == 5000


def test_plain_numeric_altitude_string_is_accepted() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0, "altitude": "8000"},
    ]

    result = calculate_fuel({"flight_plan": _plan(route=route)})

    assert result["fuel_state"]["legs"][0]["altitude_ft"] == 8000


def test_unparseable_altitude_falls_back_to_cruise_altitude() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0, "altitude": "not-a-number"},
    ]

    result = calculate_fuel({"flight_plan": _plan(route=route, cruise_altitude=7000)})

    assert result["fuel_state"]["legs"][0]["altitude_ft"] == 7000


def test_headwind_increases_burn() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0, "wind": {"headwind": 30.0}},
    ]

    result = calculate_fuel({"flight_plan": _plan(route=route)})

    assert result["fuel_state"]["total_burn"] > 4.55


def test_multiple_legs_are_summed() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0},
        {"name": "KCCC", "lat": 0.0, "lng": 2.0},
    ]

    result = calculate_fuel({"flight_plan": _plan(route=route)})

    assert len(result["fuel_state"]["legs"]) == 2
    assert result["fuel_state"]["total_burn"] == pytest.approx(9.1, abs=0.05)


def test_ifr_reserve_is_computed_from_the_aircraft_burn_rate() -> None:
    result = calculate_fuel({"flight_plan": _plan(flight_rules="IFR")})

    assert result["fuel_state"]["reserve_required"] == pytest.approx(6.38)
