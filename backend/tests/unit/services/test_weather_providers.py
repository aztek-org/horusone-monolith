"""Unit tests for the raw METAR/TAF provider seam.

The Aviation Weather Center provider is tested with an in-process
``httpx.MockTransport``. No external HTTP request is issued.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.services.external.weather_providers import (
    AviationWeatherProvider,
    MockWeatherProvider,
    build_weather_provider,
)
from app.services.external.weather_service import WeatherService
from app.services.llm.tools.weather_tools import MOCK_METARS, MOCK_TAFS

FIXTURES = Path(__file__).parents[2] / "fixtures" / "weather"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text().strip()


def _settings(**weather: object) -> Settings:
    return Settings(_env_file=None, environment="testing", weather=weather)


def _transport(
    requests: list[httpx.Request], responses: dict[str, str]
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        endpoint = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, text=responses[endpoint])

    return httpx.MockTransport(handler)


class TestMockWeatherProvider:
    @pytest.mark.asyncio
    async def test_returns_canned_reports(self) -> None:
        provider = MockWeatherProvider()

        assert await provider.fetch_raw_metar("KJFK") == MOCK_METARS["KJFK"]
        assert "TAF KJFK" in await provider.fetch_raw_taf("KJFK")

    @pytest.mark.asyncio
    async def test_normalises_station_identifiers(self) -> None:
        provider = MockWeatherProvider()

        assert await provider.fetch_raw_metar("  kjfk ") == MOCK_METARS["KJFK"]
        assert (await provider.fetch_raw_taf("kord")).startswith("TAF KORD")


class TestAviationWeatherProvider:
    @pytest.mark.asyncio
    async def test_uses_documented_awc_endpoints_and_parameters(self) -> None:
        requests: list[httpx.Request] = []
        transport = _transport(
            requests,
            {
                "metar": _fixture("kjfk_metar.txt"),
                "taf": _fixture("kjfk_taf.txt"),
            },
        )
        provider = AviationWeatherProvider(
            client_factory=lambda: httpx.AsyncClient(transport=transport)
        )

        metar = await provider.fetch_raw_metar(" kjfk ")
        taf = await provider.fetch_raw_taf("KJFK")

        assert metar == _fixture("kjfk_metar.txt")
        assert taf == _fixture("kjfk_taf.txt")
        assert [(request.url.path, request.url.params["format"]) for request in requests] == [
            ("/api/data/metar", "raw"),
            ("/api/data/taf", "raw"),
        ]
        assert requests[0].url.params["ids"] == "KJFK"
        assert requests[1].url.params["ids"] == "KJFK"

    @pytest.mark.asyncio
    async def test_strips_upstream_response_text(self) -> None:
        transport = _transport(
            [],
            {
                "metar": "\nKJFK 151856Z 28012KT 10SM CLR 22/12 A3012\n",
                "taf": "TAF",
            },
        )
        provider = AviationWeatherProvider(
            client_factory=lambda: httpx.AsyncClient(transport=transport)
        )

        assert await provider.fetch_raw_metar("KJFK") == (
            "KJFK 151856Z 28012KT 10SM CLR 22/12 A3012"
        )

    @pytest.mark.asyncio
    async def test_upstream_errors_propagate_to_the_service(self) -> None:
        transport = httpx.MockTransport(lambda _: httpx.Response(404))
        provider = AviationWeatherProvider(
            client_factory=lambda: httpx.AsyncClient(transport=transport)
        )

        with pytest.raises(httpx.HTTPStatusError):
            await provider.fetch_raw_metar("KJFK")


class TestBuildWeatherProvider:
    def test_defaults_to_the_deterministic_mock(self) -> None:
        provider = build_weather_provider(_settings())

        assert isinstance(provider, MockWeatherProvider)

    def test_production_auto_selects_aviation_weather(self) -> None:
        provider = build_weather_provider(
            Settings(
                _env_file=None,
                environment="production",
                database_url="postgresql+asyncpg://x/y",
                redis_url="redis://x",
                cors_origins="https://app.example",
                keycloak_issuer_url="https://auth.example/realms/horus",
                llm={
                    "provider": "ollama",
                    "base_url": "http://llm:11434",
                    "model": "llama3.2:3b",
                    "embedding_model": "nomic-embed-text",
                },
            )
        )

        assert isinstance(provider, AviationWeatherProvider)
        assert provider.provider == "aviationweather"

    def test_recognises_provider_aliases(self) -> None:
        provider = build_weather_provider(_settings(provider="NOAA "))

        assert isinstance(provider, AviationWeatherProvider)
        service = WeatherService(provider)
        assert service.provider == "aviationweather"

    def test_unknown_provider_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown WEATHER_PROVIDER 'checkwx'"):
            build_weather_provider(_settings(provider="checkwx"))

    @pytest.mark.asyncio
    async def test_configured_base_url_is_used(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requests: list[httpx.Request] = []
        transport = _transport(requests, {"metar": "METAR", "taf": "TAF"})
        monkeypatch.setattr(
            AviationWeatherProvider,
            "_default_client",
            lambda self: httpx.AsyncClient(transport=transport),
        )
        provider = build_weather_provider(
            _settings(provider="aviationweather", base_url="https://weather.test/api/data")
        )

        assert await provider.fetch_raw_metar("KJFK") == "METAR"
        assert requests[0].url.path == "/api/data/metar"
        assert str(requests[0].url.host) == "weather.test"
