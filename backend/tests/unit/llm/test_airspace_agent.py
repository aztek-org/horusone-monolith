"""Unit tests for the deterministic airspace-restriction agent."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.agents import airspace_agent
from app.services.llm.agents.airspace_agent import check_airspace_restrictions
from app.services.llm.state import Severity

KJFK = (40.6413, -73.7781)
OVERSEA = (0.0, 0.0)


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "route": [
            {"name": "KJFK", "lat": KJFK[0], "lng": KJFK[1], "altitude": 3000},
            {"name": "OVERSEA", "lat": OVERSEA[0], "lng": OVERSEA[1], "altitude": 5000},
        ],
        "cruise_altitude": 5000,
    }
    plan.update(overrides)
    return plan


def _results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in result["validation_results"] if r["agent"] == "airspace"]


def test_class_b_entry_requires_clearance_and_equipment() -> None:
    result = check_airspace_restrictions({"flight_plan": _plan()})

    info = result["airspace_info"]
    assert len(info["intersections"]) == 2
    assert "ATC clearance required" in info["required_clearances"]
    assert "Transponder with Mode C" in info["required_equipment"]
    assert "Two-way radio" in info["required_equipment"]

    messages = [r["message"] for r in _results(result)]
    assert any("enters Class B airspace near: KJFK" in m for m in messages)


def test_route_outside_class_b_reports_no_intersection() -> None:
    route = [{"name": "OVERSEA", "lat": 0.0, "lng": 0.0, "altitude": 3000}]

    result = check_airspace_restrictions({"flight_plan": _plan(route=route)})

    info = result["airspace_info"]
    assert info["required_clearances"] == []
    assert info["required_equipment"] == []
    messages = [r["message"] for r in _results(result)]
    assert any("does not intersect Class B" in m for m in messages)


def test_empty_route_produces_empty_airspace_info() -> None:
    result = check_airspace_restrictions({"flight_plan": _plan(route=[])})

    assert result["airspace_info"]["intersections"] == []
    assert result["airspace_info"]["required_clearances"] == []


def test_string_altitude_is_coerced_to_int() -> None:
    route = [{"name": "KJFK", "lat": KJFK[0], "lng": KJFK[1], "altitude": "2000"}]

    result = check_airspace_restrictions({"flight_plan": _plan(route=route)})

    assert result["airspace_info"]["intersections"][0]["class"] == "B"


@pytest.mark.parametrize(
    ("airspace_class", "expected_equipment"),
    [
        ("B", ["Transponder with Mode C", "Two-way radio"]),
        ("C", ["Transponder with Mode C", "Two-way radio"]),
        ("D", ["Two-way radio"]),
        ("E", []),
    ],
)
def test_equipment_requirements_per_airspace_class(
    monkeypatch: pytest.MonkeyPatch,
    airspace_class: str,
    expected_equipment: list[str],
) -> None:
    def _fake_route_airspace(waypoints: list[dict]) -> list[dict[str, Any]]:
        return [
            {
                "class": airspace_class,
                "waypoint_name": "TEST",
                "requirements": [f"{airspace_class} requirement"],
            }
        ]

    monkeypatch.setattr(airspace_agent, "get_route_airspace", _fake_route_airspace)

    result = check_airspace_restrictions({"flight_plan": _plan()})

    assert result["airspace_info"]["required_equipment"] == expected_equipment
    assert result["airspace_info"]["required_clearances"] == [f"{airspace_class} requirement"]


def test_class_e_only_emits_the_info_result() -> None:
    route = [{"name": "OVERSEA", "lat": 0.0, "lng": 0.0, "altitude": 3000}]

    result = check_airspace_restrictions({"flight_plan": _plan(route=route)})

    results = _results(result)
    assert len(results) == 1
    assert results[0]["severity"] == Severity.INFO.value
    assert results[0]["passed"] is True
