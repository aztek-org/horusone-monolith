"""The flight-plan parser asks the configured provider, not an Ollama endpoint.

Before this refactor the parser spoke Ollama's wire protocol itself, so with
``LLM_PROVIDER=groq`` it posted to ``<groq-url>/api/generate`` and fell through
to keyword extraction.  These tests pin the provider-independent path.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.config import Settings
from app.llm import SceneConstraints
from app.llm.adapters.fake_adapter import FakeAdapter
from app.llm.routing import FallbackLLM
from app.llm.types import (
    GenerationRequest,
    GenerationResult,
    LLMTransientError,
    LLMUnavailableError,
)
from app.services.flight_plan_parser import FlightPlanParser

PARSED = {
    "departure_icao": "kjfk",
    "arrival_icao": "kbos",
    "alternate_icao": "kord",
    "aircraft_type": "C172",
    "cruise_altitude": "5500",
    "flight_rules": "vfr",
}


class _StubLLM:
    """Records every request and replies with a canned body."""

    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self.calls: list[GenerationRequest] = []
        self._text = text
        self._error = error

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        return GenerationResult(
            text=self._text or "",
            provider="stub",
            model="stub-model",
            fallback_used=False,
        )

    async def embed(self, texts: list[str]) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


@pytest.mark.asyncio
async def test_parse_requests_generation_for_the_flight_plan_purpose() -> None:
    llm = _StubLLM(json.dumps(PARSED))
    parser = FlightPlanParser(llm)

    parsed = await parser.from_text("VFR from KJFK to KBOS at 5500 in a C172")

    assert len(llm.calls) == 1
    request = llm.calls[0]
    assert request.purpose == "flight_plan_parse"
    assert "KJFK" in request.prompt
    assert parsed["departure_icao"] == "KJFK"
    assert parsed["arrival_icao"] == "KBOS"
    assert parsed["cruise_altitude"] == 5500
    assert parsed["flight_rules"] == "VFR"


@pytest.mark.asyncio
async def test_parse_carries_the_injected_constraints_and_language() -> None:
    """Sampling and token budget travel as request fields, not wire literals."""
    llm = _StubLLM(json.dumps(PARSED))
    constraints = SceneConstraints(temperature=0.0, max_output_tokens=900)
    parser = FlightPlanParser(llm, constraints=constraints, language="es")

    await parser.from_text("VFR desde KJFK a KBOS")

    assert llm.calls[0].scene_constraints is constraints
    assert llm.calls[0].language == "es"


@pytest.mark.asyncio
async def test_parse_never_opens_an_http_client() -> None:
    """No provider is contacted directly; the module owns every request."""
    llm = _StubLLM(json.dumps(PARSED))
    parser = FlightPlanParser(llm)

    assert not hasattr(parser, "_call_ollama")
    assert not hasattr(parser, "ollama_base_url")
    assert await parser.from_text("KJFK to KBOS") is not None


@pytest.mark.asyncio
async def test_parse_falls_back_to_keywords_when_the_provider_fails() -> None:
    for error in (
        LLMUnavailableError("no provider", fallback_attempted=False),
        LLMTransientError("timeout"),
        RuntimeError("boom"),
    ):
        parser = FlightPlanParser(_StubLLM(error=error))

        parsed = await parser.from_text("VFR from KJFK to KBOS at 5500 in a C172")

        assert parsed["departure_icao"] == "KJFK"
        assert parsed["arrival_icao"] == "KBOS"


@pytest.mark.asyncio
async def test_parse_falls_back_when_the_provider_returns_no_json() -> None:
    parser = FlightPlanParser(_StubLLM("I cannot help with that."))

    parsed = await parser.from_text("VFR from KJFK to KBOS at 5500 in a C172")

    assert parsed["departure_icao"] == "KJFK"


def test_parser_builds_the_configured_provider_when_none_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unmigrated route still gets a working, provider-aware parser."""
    settings = Settings(
        _env_file=None,
        environment="testing",
        llm={"provider": "fake", "base_url": "http://unused", "model": "fake"},
    )
    monkeypatch.setattr(
        "app.services.flight_plan_parser.get_settings", lambda: settings
    )

    parser = FlightPlanParser()

    assert isinstance(parser.llm, FallbackLLM)
    assert parser.llm.provider == "fake"


@pytest.mark.asyncio
async def test_legacy_provider_arguments_cannot_redirect_the_request() -> None:
    """``ollama_base_url``/``model`` are redundant with ``LLM_*`` settings.

    The only unmigrated caller still passes them, so they stay accepted, but
    they must not select a provider or an endpoint: the injected module and the
    ``LLM_*`` settings are the only sources of truth.
    """
    llm = _StubLLM(json.dumps(PARSED))
    parser = FlightPlanParser(
        llm,
        ollama_base_url="http://someone-elses-ollama:11434",
        model="someone-elses-model",
    )

    await parser.from_text("KJFK to KBOS")

    assert len(llm.calls) == 1
    assert parser.llm is llm
    assert not hasattr(parser, "model")
    assert not hasattr(parser, "ollama_base_url")


@pytest.mark.asyncio
async def test_injected_module_is_used_verbatim() -> None:
    llm = FakeAdapter()
    parser = FlightPlanParser(llm)

    await parser.from_text("KJFK to KBOS")

    assert parser.llm is llm
    assert [call.purpose for call in llm.calls] == ["flight_plan_parse"]
