"""End-to-end tests for the deterministic pre-flight validation graph."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.services.llm.graphs.validation_graph import (
    _check_all_passed,
    build_validation_graph,
    state_org_id,
)
from app.services.llm.state import Severity

VALID_PLAN: dict[str, Any] = {
    "departure_icao": "KLAX",
    "arrival_icao": "KSFO",
    "route": [
        {"name": "KLAX", "lat": 33.94, "lng": -118.40},
        {"name": "KSFO", "lat": 37.62, "lng": -122.38},
    ],
    "aircraft_type": "C172",
    "fuel_on_board": 40.0,
    "fuel_reserve": 5.0,
    "total_weight": 2000.0,
    "max_weight": 2450.0,
    "flight_rules": "VFR",
    "cruise_altitude": 3500,
}


class TestStateOrgId:
    def test_missing_org_is_none(self) -> None:
        assert state_org_id({}) is None

    @pytest.mark.parametrize("value", [None, ""])
    def test_empty_org_is_none(self, value: Any) -> None:
        assert state_org_id({"org_id": value}) is None

    def test_string_org_is_parsed_to_uuid(self) -> None:
        org = uuid.uuid4()

        assert state_org_id({"org_id": str(org)}) == org

    def test_uuid_org_is_returned_unchanged(self) -> None:
        org = uuid.uuid4()

        assert state_org_id({"org_id": org}) is org


class TestCheckAllPassed:
    def test_critical_failure_fails_the_verdict(self) -> None:
        state = {
            "validation_results": [
                {
                    "agent": "gatekeeper",
                    "passed": False,
                    "severity": Severity.CRITICAL.value,
                    "message": "bad",
                    "details": None,
                }
            ]
        }

        assert _check_all_passed(state) == {
            "validation_passed": False,
            "phase": "validation",
        }

    def test_warning_failure_still_passes(self) -> None:
        state = {
            "validation_results": [
                {
                    "agent": "airspace",
                    "passed": False,
                    "severity": Severity.WARNING.value,
                    "message": "warn",
                    "details": None,
                }
            ]
        }

        assert _check_all_passed(state)["validation_passed"] is True

    def test_no_results_passes(self) -> None:
        result = _check_all_passed({})

        assert result == {"validation_passed": True, "phase": "pre_flight"}


async def test_valid_plan_passes_the_whole_pipeline() -> None:
    graph = build_validation_graph()

    result = await graph.ainvoke({"flight_plan": VALID_PLAN, "validation_results": []})

    assert result["validation_passed"] is True
    assert result["phase"] == "pre_flight"
    agents = {r["agent"] for r in result["validation_results"]}
    assert agents == {
        "gatekeeper",
        "weather",
        "fuel",
        "route",
        "airspace",
        "performance",
    }
    assert result["weather"]["flight_category"] == "VFR"
    assert result["fuel_state"]["sufficient"] is True


async def test_missing_flight_plan_fails_the_whole_pipeline() -> None:
    graph = build_validation_graph()

    result = await graph.ainvoke({"flight_plan": None, "validation_results": []})

    assert result["validation_passed"] is False
    assert result["phase"] == "validation"
