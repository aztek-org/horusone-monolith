"""Live session graph for one injected, Scene-configured ATC exchange.

```mermaid
graph TD
    START([START]) --> understand_input
    understand_input --> retrieve_knowledge
    retrieve_knowledge --> check_emergency{Emergency?}
    check_emergency -->|Yes| emergency_handler
    check_emergency -->|No| generate_atc_response
    emergency_handler --> evaluate_exchange
    generate_atc_response --> evaluate_exchange
    evaluate_exchange --> END([END])
```

The graph handles a single pilot-to-ATC exchange. The caller may compile it
with an interrupt before response generation for instructor review.

``retrieve_knowledge`` runs once per exchange on every path. It queries the
injected ``KnowledgeRetriever`` with the pilot transmission, scoped by tenant
and the Scene's ``knowledge_refs``, and records the matched chunks as
``citations``. The generation node grounds its prompt on the retrieved text
(each chunk's snippet); the citation records the chunk's coordinates. The
Scene prompt grammar is untouched — reference material is prepended exactly
like recent history, not injected through a template placeholder.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.knowledge.types import KnowledgeRetriever, RetrievalQuery
from app.llm import GenerationRequest, LLMModule
from app.services.llm.agents.emergency_agent import detect_emergency, handle_emergency
from app.services.llm.graphs.validation_graph import state_org_id
from app.services.llm.scenes.registry import SceneConfig
from app.services.llm.state import HorusState, advance_exchange

logger = logging.getLogger(__name__)
_CONTROLLED_PROMPT_KEYS = frozenset({"pilot_message"})
_RETRIEVAL_TOP_K = 5
_CITATION_SNIPPET_CHARS = 600


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


def citation_from_chunk(chunk: Any) -> dict[str, Any]:
    """Turn one retrieved chunk into a JSON-serializable citation pointer.

    The chunk is stored as coordinates (id, document, page, section) plus a
    bounded ``snippet`` so session state stays small; the full text never enters
    the checkpoint.
    """
    content = str(getattr(chunk, "content", "") or "")
    return {
        "chunk_id": str(getattr(chunk, "chunk_id", "")),
        "document_id": str(getattr(chunk, "document_id", "")),
        "title": str(getattr(chunk, "title", "") or ""),
        "page": getattr(chunk, "page", None),
        "section": getattr(chunk, "section", None),
        "snippet": content[:_CITATION_SNIPPET_CHARS],
    }


def render_references(state: HorusState) -> str:
    """Render retrieved snippets as a prompt preamble, or ``""`` when empty."""
    citations = state.get("citations") or []
    if not citations:
        return ""
    lines = [
        f"- {citation.get('title') or 'Knowledge'}: {citation.get('snippet') or ''}".strip()
        for citation in citations
    ]
    return "\nReference material (cite if used):\n" + "\n".join(lines) + "\n"


def _retrieve_knowledge_factory(knowledge: KnowledgeRetriever | None, scene: SceneConfig) -> Any:
    """Create the retrieval node, or a no-op when no retriever is injected."""

    if knowledge is None:

        def _no_knowledge(state: HorusState) -> dict[str, Any]:
            return {}

        return _no_knowledge

    async def _retrieve_knowledge(state: HorusState) -> dict[str, Any]:
        query = RetrievalQuery(
            query=(state.get("pilot_message") or scene.name),
            org_id=state_org_id(state),
            top_k=_RETRIEVAL_TOP_K,
            knowledge_refs=list(state.get("knowledge_refs") or []),
            mode="hybrid",
        )
        chunks = await knowledge.search(query)
        return {
            "citations": [citation_from_chunk(chunk) for chunk in chunks],
            "retrieved_chunk_ids": [str(getattr(chunk, "chunk_id", chunk)) for chunk in chunks],
        }

    return _retrieve_knowledge


def _prompt_context(scene: SceneConfig, context: dict[str, Any]) -> dict[str, Any]:
    """Fill Scene context while reserving controlled keys for the current exchange.

    Context supplied by callers is untrusted for prompt control. Controlled
    values, currently ``pilot_message``, are therefore always applied after
    and take precedence over same-named context keys.
    """
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
    untrusted_context = {
        key: value for key, value in context.items() if key not in _CONTROLLED_PROMPT_KEYS
    }
    return {**scene_context, **untrusted_context}


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "type", ""))


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", message))


def _render_recent_exchanges(messages: list[Any] | None) -> str:
    """Render at most the last three pilot/ATC exchanges for continuity."""
    recent_messages = list(messages or [])[-6:]
    if not recent_messages:
        return ""

    history_lines = []
    for message in recent_messages:
        label = "Pilot" if _message_role(message) in {"human", "user"} else "ATC"
        history_lines.append(f"{label}: {_message_content(message)}")
    return "\nRecent exchanges:\n" + "\n".join(history_lines) + "\n"


def _clean_response(response: str) -> str:
    """Normalize provider text for concise, role-free ATC speech."""
    cleaned = " ".join(response.strip().split())
    prefixes = ("ATC:", "Tower:", "Approach:", "Ground:", "Response:", "Controller:")
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned


def _generate_atc_response_factory(llm: LLMModule, scene: SceneConfig) -> Any:
    """Create the response node with its LLM and Scene dependencies injected."""

    async def _generate_atc_response(state: HorusState) -> dict[str, Any]:
        context = _prompt_context(scene, state.get("context") or {})
        prompt = scene.prompt_template.format(
            **context,
            pilot_message=state.get("pilot_message") or "",
        )
        history = _render_recent_exchanges(state.get("messages"))
        preamble = f"{history}{render_references(state)}"
        if preamble:
            prompt = f"{preamble}{prompt}"
        request = GenerationRequest(
            prompt=prompt,
            purpose="atc_response",
            scene_constraints=scene.constraints,
            language=state.get("language", "en"),
        )
        result = await llm.generate(request)
        return {
            "atc_response": _clean_response(result.text),
            "llm_provider": result.provider,
            "llm_model": result.model,
            "llm_fallback_used": result.fallback_used,
        }

    return _generate_atc_response


def _evaluate_exchange(state: HorusState) -> dict[str, Any]:
    """Evaluate the exchange and update session counters."""
    return {
        **advance_exchange(state),
        "performance_notes": list(state.get("performance_notes") or []),
    }


def build_live_session_graph(
    llm: LLMModule,
    scene: SceneConfig,
    interrupt_before_response: bool,
    knowledge: KnowledgeRetriever | None = None,
) -> CompiledStateGraph:
    """Build and compile a live-session graph with injected dependencies.

    Args:
        llm: Provider-independent language-model module.
        scene: Versioned Scene containing the prompt and constraints.
        interrupt_before_response: Pause before generating the ATC response.
        knowledge: Optional retriever; when supplied, each exchange records the
            chunks it drew on as citations and grounds the prompt on their text.
    """
    graph = StateGraph(HorusState)
    graph.add_node("understand_input", _understand_input)
    graph.add_node("retrieve_knowledge", _retrieve_knowledge_factory(knowledge, scene))
    graph.add_node("emergency_handler", handle_emergency)
    graph.add_node(
        "generate_atc_response",
        _generate_atc_response_factory(llm, scene),
    )
    graph.add_node("evaluate_exchange", _evaluate_exchange)

    graph.set_entry_point("understand_input")
    graph.add_edge("understand_input", "retrieve_knowledge")
    graph.add_conditional_edges(
        "retrieve_knowledge",
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
        compile_kwargs["interrupt_before"] = [
            "generate_atc_response",
            "emergency_handler",
        ]

    compiled = graph.compile(**compile_kwargs)
    logger.info(
        "Live session graph compiled (scene=%s, HITL=%s)",
        scene.version,
        interrupt_before_response,
    )
    return compiled
