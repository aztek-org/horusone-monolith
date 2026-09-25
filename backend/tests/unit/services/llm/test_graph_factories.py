"""Unit tests for dependency-injected graph factories."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from app.llm.adapters.fake_adapter import FakeAdapter
from app.services.llm.graphs.live_session_graph import build_live_session_graph
from app.services.llm.graphs.scoring_graph import build_scoring_graph
from app.services.llm.graphs.validation_graph import build_validation_graph
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneConfig
from app.services.llm.state import HorusState


class RecordingRetriever:
    """Minimal structural KnowledgeRetriever for graph integration tests."""

    def __init__(self) -> None:
        self.queries: list[Any] = []

    async def search(self, query: Any) -> list[Any]:
        self.queries.append(query)
        return [
            type(
                "RetrievedChunk",
                (),
                {"chunk_id": "chunk-weather-1"},
            )()
        ]


def _live_state(pilot_message: str = "Requesting departure clearance") -> HorusState:
    return {
        "messages": [],
        "pilot_message": pilot_message,
        "atc_response": "",
        "context": {},
        "language": "en",
        "exchange_count": 0,
        "session_phase_detail": "briefing",
        "performance_notes": [],
    }


def test_live_graph_compiles_without_network() -> None:
    graph = build_live_session_graph(FakeAdapter(), DEFAULT_SCENE, False)

    assert graph is not None


def test_live_graph_uses_injected_llm_and_scene_constraints() -> None:
    llm = FakeAdapter()
    scene = replace(DEFAULT_SCENE, prompt_template="[[reply:{pilot_message}]]")
    graph = build_live_session_graph(llm, scene, False)

    result = asyncio.run(graph.ainvoke(_live_state()))

    assert result["atc_response"] == "Requesting departure clearance"
    assert result["llm_provider"] == "fake"
    assert result["llm_model"] == "fake"
    assert result["llm_fallback_used"] is False
    assert len(llm.calls) == 1
    assert llm.calls[0].purpose == "atc_response"
    assert llm.calls[0].scene_constraints is scene.constraints
    assert llm.calls[0].language == "en"


@pytest.mark.asyncio
async def test_controlled_pilot_message_overrides_context_collision() -> None:
    scene = replace(DEFAULT_SCENE, prompt_template="[[reply:{pilot_message}]]")
    graph = build_live_session_graph(FakeAdapter(), scene, False)

    result = await graph.ainvoke(
        _live_state("Actual current transmission") | {"context": {"pilot_message": "Stale value"}}
    )

    assert result["atc_response"] == "Actual current transmission"


def test_live_graph_supports_an_empty_context() -> None:
    graph = build_live_session_graph(FakeAdapter(), DEFAULT_SCENE, False)

    result = asyncio.run(graph.ainvoke(_live_state()))

    assert result["atc_response"] == "Say again, transmission unclear."


@pytest.mark.parametrize(
    ("raw_response", "clean_response"),
    [
        ("ATC: Cleared for takeoff runway 27.", "Cleared for takeoff runway 27."),
        ("Tower: Contact approach on 123.4.", "Contact approach on 123.4."),
        (
            "Approach: Descend and maintain flight level 250.",
            "Descend and maintain flight level 250.",
        ),
        ("Ground: Taxi to runway 27 via Alpha.", "Taxi to runway 27 via Alpha."),
        ("Response: Roger, maintain heading 270.", "Roger, maintain heading 270."),
        (
            "Controller: Reduce speed to 180 knots.",
            "Reduce speed to 180 knots.",
        ),
        (
            "  Tower:   Contact\n  approach   on 123.4.  ",
            "Contact approach on 123.4.",
        ),
        ("ATC: Tower: Contact approach on 123.4.", "Contact approach on 123.4."),
    ],
)
@pytest.mark.asyncio
async def test_live_graph_normalizes_generated_response(
    raw_response: str,
    clean_response: str,
) -> None:
    scene = replace(
        DEFAULT_SCENE,
        prompt_template=f"{DEFAULT_SCENE.prompt_template}\n[[reply:{raw_response}]]",
    )
    graph = build_live_session_graph(FakeAdapter(), scene, False)

    result = await graph.ainvoke(_live_state())

    assert result["atc_response"] == clean_response


@pytest.mark.asyncio
async def test_emergency_routing_bypasses_llm_generation() -> None:
    llm = FakeAdapter()
    graph = build_live_session_graph(llm, DEFAULT_SCENE, False)

    result = await graph.ainvoke(_live_state("MAYDAY MAYDAY engine failure"))

    assert "roger engine failure" in result["atc_response"]
    assert result["is_emergency"] is True
    assert result["exchange_count"] == 1
    assert llm.calls == []


@pytest.mark.asyncio
async def test_interrupt_before_response_waits_for_generation() -> None:
    llm = FakeAdapter()
    graph = build_live_session_graph(llm, DEFAULT_SCENE, True)

    result = await graph.ainvoke(_live_state())

    assert result["atc_response"] == ""
    assert result["exchange_count"] == 0
    assert result["is_emergency"] is False
    assert llm.calls == []


@pytest.mark.parametrize(
    ("pilot_message", "expected_note"),
    [
        ("Roger, over and out", "over and out"),
        ("Tower, please grant clearance", "avoid 'please'"),
        ("Uh tower, requesting taxi", "Hesitation detected"),
    ],
)
@pytest.mark.asyncio
async def test_understand_node_reports_phraseology_notes(
    pilot_message: str,
    expected_note: str,
) -> None:
    graph = build_live_session_graph(FakeAdapter(), DEFAULT_SCENE, False)

    result = await graph.ainvoke(_live_state(pilot_message))

    assert any(expected_note in note for note in result["performance_notes"])


@pytest.mark.asyncio
async def test_first_exchange_advances_briefing_to_taxi() -> None:
    graph = build_live_session_graph(FakeAdapter(), DEFAULT_SCENE, False)

    result = await graph.ainvoke(_live_state())

    assert result["session_phase_detail"] == "taxi"
    assert result["phase"] == "active"


def test_no_module_global_llm() -> None:
    import app.services.llm.graphs.live_session_graph as module

    assert not hasattr(module, "_llm")


@pytest.mark.asyncio
async def test_validation_graph_records_retrieved_chunk_ids() -> None:
    retriever = RecordingRetriever()
    graph = build_validation_graph(retriever)
    state: HorusState = {
        "flight_plan": {
            "departure_icao": "KLAX",
            "arrival_icao": "KSFO",
            "flight_rules": "VFR",
            "aircraft_type": "C172",
            "fuel_on_board": 30.0,
            "fuel_reserve": 5.0,
            "total_weight": 2000.0,
            "max_weight": 2450.0,
            "cruise_altitude": 3500,
            "route": [
                {"name": "KLAX", "lat": 33.94, "lng": -118.40},
                {"name": "KSFO", "lat": 37.62, "lng": -122.38},
            ],
        },
        "validation_results": [],
    }

    result = await graph.ainvoke(state)

    assert result["retrieved_chunk_ids"] == ["chunk-weather-1"]
    assert len(retriever.queries) == 1
    query_text = retriever.queries[0].query
    assert "departure_icao KLAX" in query_text
    assert "arrival_icao KSFO" in query_text
    assert "flight_rules VFR" in query_text


def test_scoring_graph_compiles() -> None:
    graph = build_scoring_graph()

    assert graph is not None


def test_atc_prompt_text_is_owned_by_scene_config() -> None:
    from app.services.llm import prompts

    assert not hasattr(prompts, "ATC_SYSTEM_PROMPT_EN")
    assert not hasattr(prompts, "FLIGHT_CONTEXT_TEMPLATE_EN")
    assert not hasattr(prompts, "DEFAULT_FLIGHT_CONTEXT")
    assert not hasattr(prompts, "get_atc_prompt")


def test_audio_pipeline_injects_llm_and_scene_into_adapter(monkeypatch) -> None:
    import app.core.audio_pipeline as audio_pipeline_module
    from app.core.audio_pipeline import AudioPipeline

    monkeypatch.setattr(audio_pipeline_module, "WhisperSTTService", lambda: object())
    monkeypatch.setattr(audio_pipeline_module, "TTSService", lambda: object())
    monkeypatch.setattr(audio_pipeline_module, "RadioEffectsProcessor", lambda: object())
    llm = FakeAdapter()
    scene: SceneConfig = DEFAULT_SCENE

    pipeline = AudioPipeline(llm, scene)

    assert pipeline.atc_agent.llm is llm
    assert pipeline.atc_agent.scene is scene
