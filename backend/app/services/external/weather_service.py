"""Weather data service — async interface over a pluggable METAR/TAF provider.

The service owns parsing; the provider owns transport. Automatic selection
uses the NOAA Aviation Weather Center in production and the in-repo
deterministic mock elsewhere (see
``app.services.external.weather_providers``). The public interface is async so
callers never depend on which provider is configured.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.services.external.weather_providers import (
    MockWeatherProvider,
    WeatherProvider,
    build_weather_provider,
)
from app.services.llm.tools.weather_tools import (
    determine_flight_category,
    parse_metar,
    parse_taf,
)

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

#: Category priority used to pick the worst of two airports (lower is worse).
_CATEGORY_PRIORITY = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}


class WeatherService:
    """Async aviation weather boundary backed by a ``WeatherProvider``."""

    def __init__(self, provider: WeatherProvider | None = None) -> None:
        self._provider: WeatherProvider = (
            provider if provider is not None else MockWeatherProvider()
        )

    @property
    def provider(self) -> str:
        """Return the active provider's name."""
        return str(getattr(self._provider, "provider", type(self._provider).__name__))

    async def get_metar(self, icao: str) -> dict[str, Any]:
        """Fetch and parse a METAR for *icao*.

        Returns:
            Dict with ``raw``, ``station``, ``wind_dir``, ``wind_speed``,
            ``wind_gust``, ``visibility_sm``, ``ceiling_ft``,
            ``sky_layers``, ``temperature``, ``dewpoint``, ``altimeter``,
            ``flight_category``.
        """
        station = icao.upper().strip()
        try:
            raw = await self._provider.fetch_raw_metar(station)
            parsed = parse_metar(raw)
            logger.debug("METAR fetched for %s via %s: %s", station, self.provider, raw[:60])
            return parsed
        except Exception:
            logger.exception("Failed to fetch METAR for %s", station)
            return self._empty_metar(station)

    async def get_taf(self, icao: str) -> dict[str, Any]:
        """Fetch and fully parse a TAF for *icao*.

        Returns:
            The :func:`parse_taf` result: ``raw``, ``station``, ``issued``,
            ``valid``, and the list of forecast ``periods``.
        """
        station = icao.upper().strip()
        try:
            raw = await self._provider.fetch_raw_taf(station)
            parsed = parse_taf(raw)
            parsed["station"] = parsed.get("station") or station
            logger.debug("TAF fetched for %s via %s: %s", station, self.provider, raw[:60])
            return parsed
        except Exception:
            logger.exception("Failed to fetch TAF for %s", station)
            return self._empty_taf(station)

    async def get_flight_category(self, icao: str) -> str:
        """Determine the VFR/MVFR/IFR/LIFR category for *icao*.

        Returns:
            One of ``"VFR"``, ``"MVFR"``, ``"IFR"``, ``"LIFR"``.
        """
        metar = await self.get_metar(icao)
        return str(metar.get("flight_category", "VFR"))

    async def get_briefing(
        self,
        departure_icao: str,
        arrival_icao: str,
        alternate_icao: str | None = None,
    ) -> dict[str, Any]:
        """Produce a combined weather briefing for a flight.

        Returns:
            Dict with ``departure``, ``arrival``, ``alternate`` (each a
            parsed METAR dict), ``departure_taf``, ``arrival_taf`` (each a
            parsed TAF dict), and ``worst_category``.
        """
        dep = await self.get_metar(departure_icao)
        arr = await self.get_metar(arrival_icao)
        alt = await self.get_metar(alternate_icao) if alternate_icao else None

        dep_taf = await self.get_taf(departure_icao)
        arr_taf = await self.get_taf(arrival_icao)

        dep_cat = str(dep.get("flight_category", "VFR"))
        arr_cat = str(arr.get("flight_category", "VFR"))
        worst = dep_cat if self._is_worse(dep_cat, arr_cat) else arr_cat

        return {
            "departure": dep,
            "arrival": arr,
            "alternate": alt,
            "departure_taf": dep_taf,
            "arrival_taf": arr_taf,
            "worst_category": worst,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_worse(first: str, second: str) -> bool:
        return _CATEGORY_PRIORITY.get(first, 3) < _CATEGORY_PRIORITY.get(second, 3)

    @staticmethod
    def _empty_metar(icao: str) -> dict[str, Any]:
        """Return a safe fallback when the real fetch fails."""
        return {
            "raw": "",
            "station": icao,
            "wind_dir": 0,
            "wind_speed": 0,
            "wind_gust": None,
            "visibility_sm": 10,
            "ceiling_ft": None,
            "sky_layers": [],
            "temperature": None,
            "dewpoint": None,
            "altimeter": 29.92,
            "flight_category": determine_flight_category(10, None),
        }

    @staticmethod
    def _empty_taf(icao: str) -> dict[str, Any]:
        """Return a safe fallback when the real fetch fails."""
        return {
            "raw": "",
            "station": icao,
            "issued": None,
            "valid": None,
            "periods": [],
        }


def build_weather_service(settings: Settings) -> WeatherService:
    """Build a :class:`WeatherService` with the configured provider."""
    return WeatherService(build_weather_provider(settings))
