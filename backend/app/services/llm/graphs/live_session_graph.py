"""Live session graph for one injected, Scene-configured ATC exchange.

```mermaid
graph TD
    START([START]) --> understand_input
    understand_input --> check_emergency{Emergency?}
    check_emergency -->|Yes| emergency_handler
    check_emergency -->|No| generate_atc_response
    emergency_handler --> evaluate_exchange
    generate_atc_response --> evaluate_exchange
    evaluate_exchange --> END([END])
```

The graph handles a single pilot-to-ATC exchange. The caller may compile it
with an interrupt before response generation for instructor review.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.llm import GenerationRequest, LLMModule
from app.services.llm.agents.emergency_agent import detect_emergency, handle_emergency
from app.services.llm.scenes.registry import SceneConfig
from app.services.llm.state import HorusState, SessionPhase

logger = logging.getLogger(__name__)


def _understand_input(state: HorusState) -> dict[str, Any]:
    """Classify the pilot transmission and collect phraseology notes."""
    pilot_msg = (state.get("pilot_message") or "").lower()
    notes = list(state.get("performance_notes") or [])

    if "over and out" in pilot_msg:
        notes.append("Phraseology error: 'over and out' is contradictory.")
    if "please" in pilot_msg:
        notes.append("Phraseology note: avoid 'please' — use standard ICAO terms.")
    if any(word in pilot_msg for word in ("uh ", "um ", "uhh", "umm")):
        notes.append("Hesitation detected — practice for smoother transmissions.")
    if "read back" in pilot_msg or "readback" in pilot_msg:
        notes.append("Good procedure: pilot initiated readback.")
    if any(word in pilot_msg for word in ("wilco", "roger", "affirm")):
        notes.append("Good phraseology: standard acknowledgement used.")

    return {
        "performance_notes": notes,
        "is_emergency": detect_emergency(state.get("pilot_message") or ""),
    }


def _route_after_understand(state: HorusState) -> str:
    """Route emergencies to the deterministic emergency handler."""
    if state.get("is_emergency", False):
        return "emergency_handler"
    return "generate_atc_response"


def _prompt_context(scene: SceneConfig, context: dict[str, Any]) -> dict[str, Any]:
    """Fill required prompt fields from the Scene when runtime context is sparse."""
    scene_context = {
        "callsign": scene.aircraft.get("callsign", "Aircraft calling"),
        "aircraft_type": scene.aircraft.get("type", "aircraft"),
        "altitude": "",
        "heading": "",
        "speed": "",
        "position": "",
        "phase": "",
        "destination": scene.airports.get("arrival", "destination"),
        "weather": "",
    }
    return {**scene_context, **context}


def _generate_atc_response_factory(llm: LLMModule, scene: SceneConfig):
    """Create the response node with its LLM and Scene dependencies injected."""

    async def _generate_atc_response(state: HorusState) -> dict[str, Any]:
        context = _prompt_context(scene, state.get("context") or {})
        prompt = scene.prompt_template.format(
            **context,
            pilot_message=state.get("pilot_message") or "",
        )
        request = GenerationRequest(
            prompt=prompt,
            purpose="atc_response",
            scene_constraints=scene.constraints,
            language=state.get("language", "en"),
        )
        result = await llm.generate(request)
        return {
            "atc_response": result.text,
            "llm_provider": result.provider,
            "llm_model": result.model,
            "llm_fallback_used": result.fallback_used,
        }

    return _generate_atc_response


def _evaluate_exchange(state: HorusState) -> dict[str, Any]:
    """Evaluate the exchange and update session counters."""
    exchange_count = state.get("exchange_count", 0) + 1
    session_phase = state.get("session_phase_detail", "cruise")
    if session_phase == "briefing" and exchange_count >= 1:
        session_phase = "taxi"

    return {
        "exchange_count": exchange_count,
        "session_phase_detail": session_phase,
        "performance_notes": list(state.get("performance_notes") or []),
        "phase": SessionPhase.ACTIVE.value,
    }


def build_live_session_graph(
    llm: LLMModule,
    scene: SceneConfig,
    interrupt_before_response: bool,
) -> StateGraph:
    """Build and compile a live-session graph with injected dependencies.

    Args:
        llm: Provider-independent language-model module.
        scene: Versioned Scene containing the prompt and constraints.
        interrupt_before_response: Pause before generating the ATC response.
    """
    graph = StateGraph(HorusState)
    graph.add_node("understand_input", _understand_input)
    graph.add_node("emergency_handler", handle_emergency)
    graph.add_node(
        "generate_atc_response",
        _generate_atc_response_factory(llm, scene),
    )
    graph.add_node("evaluate_exchange", _evaluate_exchange)

    graph.set_entry_point("understand_input")
    graph.add_conditional_edges(
        "understand_input",
        _route_after_understand,
        {
            "emergency_handler": "emergency_handler",
            "generate_atc_response": "generate_atc_response",
        },
    )
    graph.add_edge("emergency_handler", "evaluate_exchange")
    graph.add_edge("generate_atc_response", "evaluate_exchange")
    graph.add_edge("evaluate_exchange", END)

    compile_kwargs: dict[str, Any] = {}
    if interrupt_before_response:
        compile_kwargs["interrupt_before"] = ["generate_atc_response"]

    compiled = graph.compile(**compile_kwargs)
    logger.info(
        "Live session graph compiled (scene=%s, HITL=%s)",
        scene.version,
        interrupt_before_response,
    )
    return compiled
