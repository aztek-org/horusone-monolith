"""Weather data service — async interface over mock METAR/TAF data.

In production, replace the internal mock calls with a real aviation
weather API such as `AVWX <https://avwx.rest/>`_,
`CheckWX <https://www.checkwxapi.com/>`_, or the FAA Aviation Weather
Center text data server.

The public interface is fully async so swapping in ``httpx`` calls
to a real API requires no changes to callers.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.tools.weather_tools import (
    determine_flight_category,
    fetch_metar,
    fetch_taf,
    parse_metar,
)

logger = logging.getLogger(__name__)


class WeatherService:
    """Async interface for aviation weather data.

    Currently delegates to the synchronous mock helpers in
    ``app.services.llm.tools.weather_tools``.  When a real API key is
    configured, override ``get_metar`` and ``get_taf`` to make HTTP
    calls instead.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_metar(self, icao: str) -> dict[str, Any]:
        """Fetch and parse a METAR for *icao*.

        Returns:
            Dict with ``raw``, ``station``, ``wind_dir``, ``wind_speed``,
            ``wind_gust``, ``visibility_sm``, ``ceiling_ft``,
            ``sky_layers``, ``temperature``, ``dewpoint``, ``altimeter``,
            ``flight_category``.
        """
        icao = icao.upper().strip()
        try:
            raw = fetch_metar(icao)
            parsed = parse_metar(raw)
            logger.debug("METAR fetched for %s (mock): %s", icao, raw[:60])
            return parsed
        except Exception:
            logger.exception("Failed to fetch METAR for %s", icao)
            return self._empty_metar(icao)

    async def get_taf(self, icao: str) -> dict[str, Any]:
        """Fetch a TAF for *icao*.

        Returns:
            Dict with ``raw`` and ``station`` keys.  Full TAF parsing
            is not yet implemented — the raw string is the primary
            output for now.
        """
        icao = icao.upper().strip()
        try:
            raw = fetch_taf(icao)
            logger.debug("TAF fetched for %s (mock): %s", icao, raw[:60])
            return {"raw": raw, "station": icao}
        except Exception:
            logger.exception("Failed to fetch TAF for %s", icao)
            return {"raw": "", "station": icao}

    async def get_flight_category(self, icao: str) -> str:
        """Determine the VFR/MVFR/IFR/LIFR category for *icao*.

        Convenience wrapper that fetches the METAR and extracts the
        flight category.

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
            parsed METAR dict), ``departure_taf``, ``arrival_taf``, and
            ``worst_category``.
        """
        dep = await self.get_metar(departure_icao)
        arr = await self.get_metar(arrival_icao)
        alt = await self.get_metar(alternate_icao) if alternate_icao else None

        dep_taf = await self.get_taf(departure_icao)
        arr_taf = await self.get_taf(arrival_icao)

        # Worst-case category
        priority = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}
        dep_cat = dep.get("flight_category", "VFR")
        arr_cat = arr.get("flight_category", "VFR")
        worst = dep_cat if priority.get(dep_cat, 3) < priority.get(arr_cat, 3) else arr_cat

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
