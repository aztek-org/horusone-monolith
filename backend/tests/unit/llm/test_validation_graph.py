"""End-to-end tests for the deterministic pre-flight validation graph."""

from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

import pytest

from app.services.llm.graphs.validation_graph import (
    _check_all_passed,
    build_validation_graph,
    state_org_id,
)
from app.services.llm.state import Severity

FIXTURES = Path(__file__).parents[2] / "fixtures" / "weather"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text().strip()


class _RecordingWeatherService:
    """Weather service double that records raw-report requests."""

    def __init__(self, metars: dict[str, str], tafs: dict[str, str]) -> None:
        self.metars = metars
        self.tafs = tafs
        self.metar_calls: list[str] = []
        self.taf_calls: list[str] = []

    async def get_metar(self, icao: str) -> dict[str, Any]:
        self.metar_calls.append(icao)
        return {"raw": self.metars[icao]}

    async def get_taf(self, icao: str) -> dict[str, Any]:
        self.taf_calls.append(icao)
        return {"raw": self.tafs[icao]}

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


async def test_validation_graph_uses_reports_from_the_weather_service() -> None:
    service = _RecordingWeatherService(
        {"KJFK": _fixture("kjfk_metar.txt")},
        {"KJFK": _fixture("kjfk_taf.txt")},
    )
    plan = {**VALID_PLAN, "departure_icao": "KJFK", "arrival_icao": "KJFK"}
    graph = build_validation_graph(weather=service)

    result = await graph.ainvoke({"flight_plan": plan, "validation_results": []})

    assert service.metar_calls == ["KJFK", "KJFK"]
    assert service.taf_calls == ["KJFK", "KJFK"]
    assert result["weather"]["departure_metar"] == _fixture("kjfk_metar.txt")
    assert result["weather"]["arrival_taf"] == _fixture("kjfk_taf.txt")
    assert result["weather"]["flight_category"] == "VFR"
