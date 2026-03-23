"""Live session graph — real-time ATC interaction with emergency detection.

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

This graph handles a **single pilot→ATC exchange**.  The orchestrator
invokes it once per pilot transmission; the conversation history is
maintained externally in ``HorusState.messages``.

### Human-in-the-loop

The graph supports an interrupt before ``generate_atc_response`` so
an instructor can override or modify the ATC response.  When compiled
with ``interrupt_before=["generate_atc_response"]``, the graph pauses
and returns partial state.  The instructor can then modify the state
and resume.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_community.llms import Ollama
from langgraph.graph import END, StateGraph

from app.services.llm.agents.emergency_agent import detect_emergency, handle_emergency
from app.services.llm.prompts import get_atc_prompt
from app.services.llm.state import HorusState, SessionPhase

logger = logging.getLogger(__name__)

# ── Module-level LLM reference (set by build function) ────────────────
_llm: Ollama | None = None


def _understand_input(state: HorusState) -> dict[str, Any]:
    """Classify the pilot's transmission — fast keyword matching.

    Mirrors the existing ``ATCAgent._understand_node`` logic.
    """
    pilot_msg = (state.get("pilot_message") or "").lower()
    notes = list(state.get("performance_notes") or [])

    # Detect common phraseology errors
    if "over and out" in pilot_msg:
        notes.append("Phraseology error: 'over and out' is contradictory.")
    if "please" in pilot_msg:
        notes.append("Phraseology note: avoid 'please' — use standard ICAO terms.")
    if any(w in pilot_msg for w in ("uh ", "um ", "uhh", "umm")):
        notes.append("Hesitation detected — practice for smoother transmissions.")

    # Detect positive patterns
    if "read back" in pilot_msg or "readback" in pilot_msg:
        notes.append("Good procedure: pilot initiated readback.")
    if any(w in pilot_msg for w in ("wilco", "roger", "affirm")):
        notes.append("Good phraseology: standard acknowledgement used.")

    # Check for emergency
    is_emerg = detect_emergency(state.get("pilot_message", ""))

    return {
        "performance_notes": notes,
        "is_emergency": is_emerg,
    }


def _route_after_understand(state: HorusState) -> str:
    """Conditional router: emergency handler or normal ATC response."""
    if state.get("is_emergency", False):
        return "emergency_handler"
    return "generate_atc_response"


async def _generate_atc_response(state: HorusState) -> dict[str, Any]:
    """Generate a standard ATC response using the LLM.

    Reuses the existing prompt construction from ``prompts.py``.
    """
    context = state.get("context") or {}
    language = state.get("language", "en")
    pilot_message = state.get("pilot_message", "")

    # Build conversation history context from messages
    messages = state.get("messages") or []
    history_context = ""
    if messages:
        recent = messages[-6:]  # Last 3 exchanges (pilot + atc each)
        history_lines = []
        for msg in recent:
            content = msg.content if hasattr(msg, "content") else str(msg)
            role = getattr(msg, "type", "human")
            label = "Pilot" if role == "human" else "ATC"
            history_lines.append(f"{label}: {content}")
        if history_lines:
            history_context = "\nRecent exchanges:\n" + "\n".join(history_lines) + "\n"

    full_prompt = get_atc_prompt(pilot_message, context, language)
    if history_context:
        full_prompt = full_prompt.replace(
            f'"{pilot_message}"',
            f'{history_context}\nCurrent transmission: "{pilot_message}"',
        )

    try:
        if _llm is not None:
            response = await _llm.ainvoke(full_prompt)
            atc_response = _clean_response(response)
        else:
            logger.warning("LLM not initialized — returning fallback response")
            atc_response = (
                "Repita, transmisión no clara."
                if language == "es"
                else "Say again, transmission unclear."
            )
    except Exception as e:
        logger.error("Error generating ATC response: %s", e)
        atc_response = (
            "Repita, transmisión no clara."
            if language == "es"
            else "Say again, transmission unclear."
        )

    return {"atc_response": atc_response}


def _evaluate_exchange(state: HorusState) -> dict[str, Any]:
    """Evaluate the exchange and update counters."""
    exchange_count = state.get("exchange_count", 0) + 1
    notes = list(state.get("performance_notes") or [])

    session_phase = state.get("session_phase_detail", "cruise")

    # Auto-progress from briefing to taxi after first exchange
    if session_phase == "briefing" and exchange_count >= 1:
        session_phase = "taxi"

    return {
        "exchange_count": exchange_count,
        "session_phase_detail": session_phase,
        "performance_notes": notes,
        "phase": SessionPhase.ACTIVE.value,
    }


def _clean_response(response: str) -> str:
    """Clean and format the raw LLM response."""
    cleaned = " ".join(response.strip().split())
    prefixes = ["ATC:", "Tower:", "Approach:", "Ground:", "Response:", "Controller:"]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned


def build_live_session_graph(
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "llama3:latest",
    temperature: float = 0.3,
    interrupt_before_response: bool = False,
) -> StateGraph:
    """Build and compile the live-session sub-graph.

    Args:
        ollama_base_url: Ollama server URL.
        ollama_model: Model name.
        temperature: LLM temperature (low = formulaic ATC).
        interrupt_before_response: If True, compile with HITL interrupt
            before the ATC response node.

    Returns:
        Compiled LangGraph ``StateGraph``.
    """
    global _llm  # noqa: PLW0603

    _llm = Ollama(
        base_url=ollama_base_url,
        model=ollama_model,
        temperature=temperature,
        num_predict=150,
    )

    graph = StateGraph(HorusState)

    # ── Nodes ─────────────────────────────────────────────────────
    graph.add_node("understand_input", _understand_input)
    graph.add_node("emergency_handler", handle_emergency)
    graph.add_node("generate_atc_response", _generate_atc_response)
    graph.add_node("evaluate_exchange", _evaluate_exchange)

    # ── Edges ─────────────────────────────────────────────────────
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

    # ── Compile ───────────────────────────────────────────────────
    compile_kwargs: dict[str, Any] = {}
    if interrupt_before_response:
        compile_kwargs["interrupt_before"] = ["generate_atc_response"]

    compiled = graph.compile(**compile_kwargs)
    logger.info(
        "Live session graph compiled (model=%s, HITL=%s)",
        ollama_model,
        interrupt_before_response,
    )
    return compiled
