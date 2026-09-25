"""Unit tests for the thin ATC adapter over the live-session graph."""

from __future__ import annotations

from dataclasses import replace

from app.llm.adapters.fake_adapter import FakeAdapter
from app.services.llm.atc_agent import ATCAgent
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneConfig
from app.services.llm.state import SessionPhase


def _make_agent(scene: SceneConfig = DEFAULT_SCENE) -> tuple[ATCAgent, FakeAdapter]:
    llm = FakeAdapter()
    return ATCAgent(llm, scene), llm


def test_adapter_requires_injected_llm_and_scene() -> None:
    agent, llm = _make_agent()

    assert agent.llm is llm
    assert agent.scene is DEFAULT_SCENE
    assert agent.graph is not None


async def test_generate_response_delegates_to_live_graph() -> None:
    scene = replace(DEFAULT_SCENE, prompt_template="[[reply:{pilot_message}]]")
    agent, llm = _make_agent(scene)

    response = await agent.generate_response("Ready for departure")

    assert response == "Ready for departure"
    assert len(llm.calls) == 1
    assert llm.calls[0].purpose == "atc_response"
    assert llm.calls[0].scene_constraints is scene.constraints


async def test_generate_response_preserves_conversation_history() -> None:
    agent, _ = _make_agent(replace(DEFAULT_SCENE, prompt_template="[[reply:Response {pilot_message}]]"))

    await agent.generate_response("First")
    await agent.generate_response("Second", language="es")

    assert agent.get_conversation_history() == [
        {"pilot": "First", "atc": "Response First", "language": "en"},
        {"pilot": "Second", "atc": "Response Second", "language": "es"},
    ]


async def test_generate_response_passes_language_and_context_to_llm() -> None:
    scene = replace(DEFAULT_SCENE, prompt_template="{callsign}: [[reply:roger]]")
    agent, llm = _make_agent(scene)

    response = await agent.generate_response(
        "Solicito autorización",
        context={"callsign": "N1234A"},
        language="es",
    )

    assert response == "roger"
    assert llm.calls[0].language == "es"
    assert "N1234A" in llm.calls[0].prompt


def test_reset_conversation_clears_history() -> None:
    agent, _ = _make_agent()
    agent.conversation_history = [{"pilot": "Msg", "atc": "Reply", "language": "en"}]

    agent.reset_conversation()

    assert agent.get_conversation_history() == []


async def test_default_scene_returns_provider_fallback_without_context() -> None:
    agent, llm = _make_agent()

    response = await agent.generate_response("Unclear transmission")

    assert response == "Say again, transmission unclear."
    assert len(llm.calls) == 1


async def test_emergency_response_uses_deterministic_graph_path() -> None:
    agent, llm = _make_agent()

    response = await agent.generate_response("MAYDAY engine failure")

    assert "roger engine failure" in response
    assert llm.calls == []
    assert agent.get_conversation_history()[0]["atc"] == response


def test_get_conversation_history_is_empty_for_new_adapter() -> None:
    agent, _ = _make_agent()

    assert agent.get_conversation_history() == []


def test_adapter_has_no_private_exchange_state_machine() -> None:
    agent, _ = _make_agent()

    assert not hasattr(agent, "_build_graph")
    assert not hasattr(agent, "_understand_node")
    assert not hasattr(agent, "_respond_node")
    assert not hasattr(agent, "_evaluate_node")
    assert SessionPhase.ACTIVE.value == "active"
