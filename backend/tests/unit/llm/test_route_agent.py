"""Unit tests for the deterministic route-navigation agent."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.agents.route_agent import optimize_route
from app.services.llm.state import Severity

# (0,0) → (0,1) is ~60.04 NM due east.
ROUTE = [
    {"name": "KAAA", "lat": 0.0, "lng": 0.0},
    {"name": "KBBB", "lat": 0.0, "lng": 1.0},
]


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {"route": ROUTE, "aircraft_type": "C172"}
    plan.update(overrides)
    return plan


def test_single_leg_gets_distance_heading_and_ete() -> None:
    result = optimize_route({"flight_plan": _plan()})

    info = result["route_info"]
    assert info["total_distance_nm"] == pytest.approx(60.0, abs=0.2)
    assert info["total_ete_minutes"] == pytest.approx(32.7, abs=0.2)
    leg = info["legs"][0]
    assert leg["distance_nm"] == pytest.approx(60.0, abs=0.2)
    assert leg["heading_deg"] == 90.0
    assert leg["groundspeed_kts"] == 110.0
    assert leg["ete_minutes"] == pytest.approx(32.7, abs=0.2)
    assert info["suggestions"] == []


def test_result_is_appended_to_validation_results() -> None:
    result = optimize_route({"flight_plan": _plan()})

    route_results = [r for r in result["validation_results"] if r["agent"] == "route"]
    assert len(route_results) == 1
    assert route_results[0]["passed"] is True
    assert route_results[0]["severity"] == Severity.INFO.value
    assert "Route analysed" in route_results[0]["message"]


def test_headwind_reduces_groundspeed() -> None:
    route = [
        {"name": "KAAA", "lat": 0.0, "lng": 0.0},
        {"name": "KBBB", "lat": 0.0, "lng": 1.0, "wind": {"direction": 90, "speed": 20}},
    ]

    result = optimize_route({"flight_plan": _plan(route=route)})

    assert result["route_info"]["legs"][0]["groundspeed_kts"] == 90.0


def test_cruise_speed_override_is_used() -> None:
    result = optimize_route({"flight_plan": _plan(cruise_speed=200)})

    assert result["route_info"]["legs"][0]["groundspeed_kts"] == 200.0


def test_unknown_aircraft_uses_default_true_airspeed() -> None:
    result = optimize_route({"flight_plan": _plan(aircraft_type="ZZZZ")})

    assert result["route_info"]["legs"][0]["groundspeed_kts"] == 120.0


def test_indirect_route_gets_a_direct_to_suggestion() -> None:
    route = [
        {"name": "A", "lat": 0.0, "lng": 0.0},
        {"name": "B", "lat": 1.0, "lng": 0.0},
        {"name": "C", "lat": 1.0, "lng": 1.0},
    ]

    result = optimize_route({"flight_plan": _plan(route=route)})

    suggestions = result["route_info"]["suggestions"]
    assert any("longer than direct" in s for s in suggestions)
    warning_results = [
        r for r in result["validation_results"] if r["severity"] == Severity.WARNING.value
    ]
    assert warning_results


def test_short_legs_are_flagged_for_consolidation() -> None:
    route = [
        {"name": "A", "lat": 0.0, "lng": 0.0},
        {"name": "B", "lat": 0.0, "lng": 0.05},
        {"name": "C", "lat": 0.0, "lng": 2.0},
        {"name": "D", "lat": 0.0, "lng": 3.0},
    ]

    result = optimize_route({"flight_plan": _plan(route=route)})

    assert any("consider consolidating" in s for s in result["route_info"]["suggestions"])


def test_empty_route_produces_zero_totals() -> None:
    result = optimize_route({"flight_plan": _plan(route=[])})

    assert result["route_info"]["total_distance_nm"] == 0.0
    assert result["route_info"]["total_ete_minutes"] == 0.0
    assert result["route_info"]["legs"] == []
    assert result["route_info"]["suggestions"] == []


def test_existing_validation_results_are_preserved() -> None:
    existing = {
        "agent": "prior",
        "passed": True,
        "severity": Severity.INFO.value,
        "message": "prior",
        "details": None,
    }

    result = optimize_route(
        {"flight_plan": _plan(), "validation_results": [existing]}
    )

    assert result["validation_results"][0] == existing
