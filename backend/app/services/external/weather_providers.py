"""Provider seam for raw METAR/TAF text.

``WeatherService`` is provider-agnostic: it asks a ``WeatherProvider`` for raw
report text and parses that text itself. ``MockWeatherProvider`` serves the
deterministic in-repo reports; ``AviationWeatherProvider`` talks to the NOAA
Aviation Weather Center (AWC) text data server, which serves raw METAR/TAF
without an API key.

Select the provider with ``WEATHER_PROVIDER`` (``auto``, ``mock``, or
``aviationweather``); see :func:`build_weather_provider`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://aviationweather.gov/api/data"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_USER_AGENT = "horusone-mvp-weather/0.1"


class WeatherProvider(Protocol):
    """Fetches raw METAR/TAF text for one station."""

    provider: str

    async def fetch_raw_metar(self, icao: str) -> str:
        """Return the raw METAR text for *icao*."""
        ...

    async def fetch_raw_taf(self, icao: str) -> str:
        """Return the raw TAF text for *icao*."""
        ...


class MockWeatherProvider:
    """Deterministic canned reports, used outside production."""

    provider = "mock"

    async def fetch_raw_metar(self, icao: str) -> str:
        from app.services.llm.tools.weather_tools import fetch_metar

        return fetch_metar(icao)

    async def fetch_raw_taf(self, icao: str) -> str:
        from app.services.llm.tools.weather_tools import fetch_taf

        return fetch_taf(icao)


class AviationWeatherProvider:
    """NOAA Aviation Weather Center text data server.

    The text data server is public; no API key is required.

    - METAR: ``GET {base}/metar?ids=<icao>&format=raw``
    - TAF:   ``GET {base}/taf?ids=<icao>&format=raw``
    """

    provider = "aviationweather"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") or DEFAULT_BASE_URL
        self._timeout = timeout_seconds
        self._client_factory = client_factory or self._default_client

    def _default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, headers={"User-Agent": DEFAULT_USER_AGENT})

    async def fetch_raw_metar(self, icao: str) -> str:
        """Fetch the raw METAR text for *icao*."""
        return await self._fetch("metar", "ids", icao)

    async def fetch_raw_taf(self, icao: str) -> str:
        """Fetch the raw TAF text for *icao*."""
        return await self._fetch("taf", "ids", icao)

    async def _fetch(self, endpoint: str, station_param: str, icao: str) -> str:
        station = icao.upper().strip()
        url = f"{self._base_url}/{endpoint}"
        params = {station_param: station, "format": "raw"}
        async with self._client_factory() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        return response.text.strip()


def build_weather_provider(settings: Settings) -> WeatherProvider:
    """Build the configured weather provider.

    ``auto`` (or blank) chooses the NOAA provider in production and the
    deterministic mock everywhere else. An explicit provider name always wins.
    """
    provider = settings.weather.provider.strip().lower()
    if provider in ("", "auto"):
        provider = "aviationweather" if settings.environment == "production" else "mock"
    if provider == "mock":
        return MockWeatherProvider()
    if provider in ("aviationweather", "aviation-weather", "noaa", "awc"):
        return AviationWeatherProvider(
            base_url=settings.weather.base_url,
            timeout_seconds=settings.weather.timeout_seconds,
        )
    raise ValueError(f"Unknown WEATHER_PROVIDER {provider!r}")
