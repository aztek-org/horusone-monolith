"""Unit tests for the deterministic weather analysis agent."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.agents import weather_agent
from app.services.llm.agents.weather_agent import (
    _extract_hazards,
    _generate_recommendations,
    analyze_weather,
)
from app.services.llm.state import Severity

VFR_METAR = "KAAA 151853Z 00000KT 10SM CLR 20/10 A3000"
LIFR_METAR = "KBBB 151853Z 00000KT 10SM OVC002 10/10 A2992"


def _plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "departure_icao": "KLAX",
        "arrival_icao": "KSFO",
        "flight_rules": "VFR",
    }
    plan.update(overrides)
    return plan


class TestExtractHazards:
    def test_detects_multiple_hazards_across_metar_and_taf(self) -> None:
        hazards = _extract_hazards("KJFK 28012KT 2SM TS +SN", "TAF KJFK FZRA LLWS")

        assert "Thunderstorm (TS)" in hazards
        assert "Heavy snow (+SN)" in hazards
        assert "Freezing rain (FZRA)" in hazards
        assert "Low-level wind shear (LLWS)" in hazards

    def test_plain_snow_and_heavy_snow_are_both_reported(self) -> None:
        hazards = _extract_hazards("KJFK 2SM +SN", "")

        # "SN" is a substring of "+SN", so both labels appear.
        assert "Snow (SN)" in hazards
        assert "Heavy snow (+SN)" in hazards

    def test_clean_weather_reports_no_hazards(self) -> None:
        assert _extract_hazards("KLAX 25008KT 10SM FEW025", "") == []


class TestGenerateRecommendations:
    def test_ifr_conditions_below_vfr_minimums_is_critical(self) -> None:
        recs = _generate_recommendations("IFR", [], "VFR")

        assert any("below VFR minimums" in r for r in recs)

    def test_marginal_vfr_gets_a_caution(self) -> None:
        recs = _generate_recommendations("MVFR", [], "VFR")

        assert any("marginal VFR" in r for r in recs)

    def test_ifr_under_ifr_rules_does_not_warn_about_vfr(self) -> None:
        recs = _generate_recommendations("IFR", [], "IFR")

        assert all("below VFR minimums" not in r for r in recs)

    def test_thunderstorm_hazard_adds_avoidance_advice(self) -> None:
        recs = _generate_recommendations("VFR", ["Thunderstorm (TS)"], "VFR")

        assert any("avoid area" in r for r in recs)

    def test_icing_and_fog_add_advice(self) -> None:
        recs = _generate_recommendations(
            "VFR", ["Freezing rain (FZRA)", "Fog (FG)"], "VFR"
        )

        assert any("Icing conditions" in r for r in recs)
        assert any("Reduced visibility" in r for r in recs)

    def test_wind_shear_advice_requires_a_capitalised_label(self) -> None:
        recs = _generate_recommendations("VFR", ["Wind shear reported"], "VFR")

        assert any("be prepared for go-around" in r for r in recs)

    def test_recognised_wind_shear_label_does_not_trigger_advice(self) -> None:
        # The label emitted by ``_extract_hazards`` uses a lower-case "shear",
        # so the capitalised comparison in this function never matches it.
        hazards = _extract_hazards("KJFK LLWS", "")

        assert hazards == ["Low-level wind shear (LLWS)"]
        recs = _generate_recommendations("VFR", hazards, "VFR")
        assert all("go-around" not in r for r in recs)

    def test_clean_weather_yields_an_acceptable_message(self) -> None:
        recs = _generate_recommendations("VFR", [], "VFR")

        assert recs == ["Weather conditions are acceptable for the planned flight."]


class TestAnalyzeWeather:
    def test_clear_conditions_produce_a_vfr_pass(self) -> None:
        result = analyze_weather({"flight_plan": _plan()})

        weather = result["weather"]
        assert weather["flight_category"] == "VFR"
        assert weather["hazards"] == []
        assert weather["recommendations"] == [
            "Weather conditions are acceptable for the planned flight."
        ]
        results = [r for r in result["validation_results"] if r["agent"] == "weather"]
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["severity"] == Severity.INFO.value
        assert "VFR conditions" in results[0]["message"]

    def test_marginal_conditions_are_reported_as_a_warning(self) -> None:
        result = analyze_weather(
            {"flight_plan": _plan(departure_icao="KORD", arrival_icao="KORD")}
        )

        weather = result["weather"]
        assert weather["flight_category"] == "MVFR"
        assert "Mist (visibility reduced) (BR)" in weather["hazards"]
        results = [r for r in result["validation_results"] if r["agent"] == "weather"]
        assert any("Marginal VFR" in r["message"] for r in results)
        assert any("hazards detected" in r["message"] for r in results)

    def test_worst_departure_arrival_category_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        metars = {"KAAA": VFR_METAR, "KBBB": LIFR_METAR}
        monkeypatch.setattr(weather_agent, "fetch_metar", lambda icao: metars.get(icao, ""))
        monkeypatch.setattr(weather_agent, "fetch_taf", lambda icao: "")

        result = analyze_weather(
            {"flight_plan": _plan(departure_icao="KAAA", arrival_icao="KBBB")}
        )

        assert result["weather"]["flight_category"] == "LIFR"

    def test_below_vfr_minimums_is_a_critical_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(weather_agent, "fetch_metar", lambda icao: LIFR_METAR)
        monkeypatch.setattr(weather_agent, "fetch_taf", lambda icao: "")

        result = analyze_weather({"flight_plan": _plan()})

        results = [r for r in result["validation_results"] if r["agent"] == "weather"]
        critical = [r for r in results if r["severity"] == Severity.CRITICAL.value]
        assert critical
        assert critical[0]["passed"] is False
        assert "below VFR minimums" in critical[0]["message"]

    def test_briefing_includes_hazards_and_alternate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(weather_agent, "fetch_metar", lambda icao: "KX 00000KT 2SM TS FG")
        monkeypatch.setattr(weather_agent, "fetch_taf", lambda icao: "")

        result = analyze_weather({"flight_plan": _plan(alternate_icao="KOAK")})

        briefing = result["weather"]["briefing_text"]
        assert "Departure (KLAX)" in briefing
        assert "Arrival (KSFO)" in briefing
        assert "Alternate (KOAK)" in briefing
        assert "Hazards:" in briefing
        assert "Recommendations:" in briefing

    def test_no_airports_skips_fetching(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(icao: str) -> str:  # pragma: no cover - must not run
            raise AssertionError("fetch should be skipped for empty ICAO")

        monkeypatch.setattr(weather_agent, "fetch_metar", _boom)
        monkeypatch.setattr(weather_agent, "fetch_taf", _boom)

        result = analyze_weather({"flight_plan": {}})

        assert result["weather"]["flight_category"] == "VFR"
        assert result["weather"]["alternate_metar"] is None

    def test_prefetched_reports_are_used_without_calling_fetch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(icao: str) -> str:  # pragma: no cover - must not run
            raise AssertionError("prefetched reports must bypass the mock fetch")

        monkeypatch.setattr(weather_agent, "fetch_metar", _boom)
        monkeypatch.setattr(weather_agent, "fetch_taf", _boom)
        fetched = {
            "departure_metar": LIFR_METAR,
            "arrival_metar": LIFR_METAR,
            "alternate_metar": "",
            "departure_taf": "",
            "arrival_taf": "",
        }

        result = analyze_weather({"flight_plan": _plan()}, fetched)

        assert result["weather"]["departure_metar"] == LIFR_METAR
        assert result["weather"]["flight_category"] == "LIFR"
