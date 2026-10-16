"""Unit tests for the aircraft performance / density-altitude agent."""

from __future__ import annotations

from typing import Any

from app.services.llm.agents.performance_agent import (
    AIRCRAFT_PERFORMANCE,
    _estimate_density_altitude,
    analyze_performance,
)
from app.services.llm.state import Severity


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {"aircraft_type": "C172", "cruise_altitude": 3500}
    plan.update(overrides)
    return plan


class TestEstimateDensityAltitude:
    def test_standard_day_at_sea_level_is_zero(self) -> None:
        assert _estimate_density_altitude(0, 15.0, 29.92) == 0

    def test_high_altitude_on_a_standard_day(self) -> None:
        # ISA at 5000 ft is 5 °C; standard day → density = pressure altitude.
        assert _estimate_density_altitude(5000, 5.0, 29.92) == 5000

    def test_heat_adds_one_hundred_twenty_feet_per_degree(self) -> None:
        # ISA at 5000 ft = 5 °C; +25 °C over ISA × 120 = +3000 ft.
        assert _estimate_density_altitude(5000, 30.0, 29.92) == 8000

    def test_low_altimeter_increases_pressure_altitude(self) -> None:
        # Pressure altitude 4000 ft → ISA 7 °C; 5 °C is 2 °C below ISA → −240 ft.
        assert _estimate_density_altitude(5000, 5.0, 30.92) == 3760


def test_within_ceiling_passes_without_notes() -> None:
    result = analyze_performance({"flight_plan": _plan()})

    perf = result["aircraft_performance"]
    assert perf["service_ceiling"] == 14000
    assert perf["v_speeds"]["Vy"] == 74
    assert perf["density_altitude"] is None
    assert perf["altitude_ok"] is True
    assert perf["notes"] == []

    results = [r for r in result["validation_results"] if r["agent"] == "performance"]
    assert results[0]["passed"] is True
    assert results[0]["severity"] == Severity.INFO.value


def test_above_service_ceiling_is_critical() -> None:
    result = analyze_performance({"flight_plan": _plan(cruise_altitude=15000)})

    perf = result["aircraft_performance"]
    assert perf["altitude_ok"] is False
    assert any("exceeds service ceiling" in n for n in perf["notes"])

    results = [r for r in result["validation_results"] if r["agent"] == "performance"]
    assert results[0]["passed"] is False
    assert results[0]["severity"] == Severity.CRITICAL.value


def test_high_cruise_altitude_gets_regulatory_notes() -> None:
    result = analyze_performance({"flight_plan": _plan(cruise_altitude=13000)})

    notes = result["aircraft_performance"]["notes"]
    assert any("10,000 ft" in n for n in notes)
    assert any("12,500 ft" in n for n in notes)

    results = [r for r in result["validation_results"] if r["agent"] == "performance"]
    assert results[0]["severity"] == Severity.WARNING.value


def test_unknown_aircraft_uses_default_performance() -> None:
    result = analyze_performance({"flight_plan": _plan(aircraft_type="ZZZZ")})

    perf = result["aircraft_performance"]
    assert perf["service_ceiling"] == AIRCRAFT_PERFORMANCE["DEFAULT"]["service_ceiling"]
    assert perf["v_speeds"] == AIRCRAFT_PERFORMANCE["DEFAULT"]["v_speeds"]


def test_density_altitude_is_computed_from_departure_metar() -> None:
    state = {
        "flight_plan": _plan(),
        "weather": {"departure_metar": "KLAX 151853Z 00000KT 10SM CLR 45/10 A2992"},
    }

    result = analyze_performance(state)

    perf = result["aircraft_performance"]
    assert perf["density_altitude"] == 3600
    assert any("above planned cruise" in n for n in perf["notes"])

    results = [r for r in result["validation_results"] if r["agent"] == "performance"]
    assert results[0]["severity"] == Severity.WARNING.value


def test_no_departure_metar_leaves_density_altitude_unset() -> None:
    result = analyze_performance({"flight_plan": _plan(), "weather": {}})

    assert result["aircraft_performance"]["density_altitude"] is None
