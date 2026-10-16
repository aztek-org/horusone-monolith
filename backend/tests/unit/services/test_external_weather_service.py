"""Unit tests for the external WeatherService boundary.

No network or real aviation API is contacted: the synchronous tool helpers
are patched (or exercised directly, since they ship canned mock data).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.external import weather_service as weather_module
from app.services.external.weather_service import WeatherService

# ── get_metar ──────────────────────────────────────────────────────────


class TestGetMetar:
    """Tests for WeatherService.get_metar()."""

    @pytest.mark.asyncio
    async def test_parses_canned_metar_for_known_airport(self) -> None:
        service = WeatherService()

        metar = await service.get_metar("KJFK")

        assert metar["station"] == "KJFK"
        assert metar["wind_dir"] == 280
        assert metar["wind_speed"] == 12
        assert metar["wind_gust"] == 18
        assert metar["visibility_sm"] == 10
        assert metar["ceiling_ft"] is None
        assert metar["temperature"] == 22
        assert metar["dewpoint"] == 12
        assert metar["altimeter"] == pytest.approx(30.12)
        assert metar["flight_category"] == "VFR"

    @pytest.mark.asyncio
    async def test_normalises_the_icao_before_fetching(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def _fetch(icao: str) -> str:
            seen.append(icao)
            return "KJFK 151856Z 28012KT 10SM FEW040 22/12 A3012"

        monkeypatch.setattr(weather_module, "fetch_metar", _fetch)
        service = WeatherService()

        result = await service.get_metar("  kjfk ")

        assert seen == ["KJFK"]
        assert result["station"] == "KJFK"

    @pytest.mark.asyncio
    async def test_returns_empty_metar_when_fetch_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_icao: str) -> str:
            raise RuntimeError("upstream weather failure")

        monkeypatch.setattr(weather_module, "fetch_metar", _boom)
        service = WeatherService()

        metar = await service.get_metar("KJFK")

        assert metar["raw"] == ""
        assert metar["station"] == "KJFK"
        assert metar["visibility_sm"] == 10
        assert metar["altimeter"] == pytest.approx(29.92)
        assert metar["flight_category"] == "VFR"

    @pytest.mark.asyncio
    async def test_returns_empty_metar_when_parse_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(weather_module, "fetch_metar", lambda _icao: "raw")

        def _boom(_raw: str) -> dict[str, Any]:
            raise ValueError("malformed metar")

        monkeypatch.setattr(weather_module, "parse_metar", _boom)
        service = WeatherService()

        metar = await service.get_metar("ZZZZ")

        assert metar["station"] == "ZZZZ"
        assert metar["sky_layers"] == []


# ── get_taf ────────────────────────────────────────────────────────────


class TestGetTaf:
    """Tests for WeatherService.get_taf()."""

    @pytest.mark.asyncio
    async def test_returns_raw_and_station(self) -> None:
        service = WeatherService()

        taf = await service.get_taf("kjfk")

        assert taf["station"] == "KJFK"
        assert taf["raw"].startswith("TAF KJFK")

    @pytest.mark.asyncio
    async def test_falls_back_to_blank_raw_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_icao: str) -> str:
            raise RuntimeError("taf down")

        monkeypatch.setattr(weather_module, "fetch_taf", _boom)
        service = WeatherService()

        taf = await service.get_taf("kord")

        assert taf == {"raw": "", "station": "KORD"}


# ── get_flight_category ────────────────────────────────────────────────


class TestGetFlightCategory:
    """Tests for WeatherService.get_flight_category()."""

    @pytest.mark.asyncio
    async def test_delegates_to_get_metar(self) -> None:
        from unittest.mock import AsyncMock

        service = WeatherService()
        service.get_metar = AsyncMock(  # type: ignore[method-assign]
            return_value={"flight_category": "IFR"}
        )

        category = await service.get_flight_category("KORD")

        assert category == "IFR"
        service.get_metar.assert_awaited_once_with("KORD")

    @pytest.mark.asyncio
    async def test_parses_mvfr_category_from_canned_data(self) -> None:
        service = WeatherService()

        assert await service.get_flight_category("KORD") == "MVFR"


# ── get_briefing ───────────────────────────────────────────────────────


class TestGetBriefing:
    """Tests for WeatherService.get_briefing()."""

    @pytest.mark.asyncio
    async def test_combines_departure_arrival_and_alternate(self) -> None:
        service = WeatherService()

        briefing = await service.get_briefing("KJFK", "KLAX", "KDEN")

        assert briefing["departure"]["station"] == "KJFK"
        assert briefing["arrival"]["station"] == "KLAX"
        assert briefing["alternate"]["station"] == "KDEN"
        assert briefing["departure_taf"]["station"] == "KJFK"
        assert briefing["arrival_taf"]["station"] == "KLAX"

    @pytest.mark.asyncio
    async def test_worst_category_picks_the_most_restrictive(self) -> None:
        service = WeatherService()

        # KORD is MVFR, the rest are VFR.
        briefing = await service.get_briefing("KJFK", "KORD")

        assert briefing["worst_category"] == "MVFR"

    @pytest.mark.asyncio
    async def test_alternate_is_none_when_not_supplied(self) -> None:
        service = WeatherService()

        briefing = await service.get_briefing("KJFK", "KLAX")

        assert briefing["alternate"] is None
