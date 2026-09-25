"""Horus Orchestrator — top-level multi-agent pipeline coordinator.

The ``HorusOrchestrator`` manages the full training lifecycle::

    start_session()    →  Ingestion + Validation + Pre-flight eval
    process_message()  →  Single pilot↔ATC exchange in live session
    end_session()      →  Post-flight evaluation + Scoring + Badges

It wraps three compiled LangGraph sub-graphs:

* **validation_graph** — pre-flight checks (gatekeeper, weather, fuel,
  route, airspace, performance).
* **live_session_graph** — real-time ATC interaction with emergency
  detection and optional HITL interrupt.
* **scoring_graph** — post-session student evaluation and gamification.

```mermaid
graph LR
    subgraph Ingestion
        A[start_session] --> B[validation_graph]
    end
    subgraph Live
        C[process_message] --> D[live_session_graph]
    end
    subgraph Scoring
        E[end_session] --> F[scoring_graph]
    end
    B --> C
    D --> E
```
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from typing import Any

from app.config import get_settings
from app.llm import build_llm
from app.services.llm.graphs.live_session_graph import build_live_session_graph
from app.services.llm.graphs.scoring_graph import build_scoring_graph
from app.services.llm.graphs.validation_graph import build_validation_graph
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.state import HorusState, SessionPhase

logger = logging.getLogger(__name__)


class HorusOrchestrator:
    """Main orchestrator that manages the full Horus training pipeline.

    Instantiate once at application startup and reuse across requests.
    Each session is identified by a ``session_id`` and its state is
    stored in an in-memory dict (swap for Redis/Postgres in production).

    Parameters
    ----------
    ollama_base_url : str, optional
        Override for the Ollama REST endpoint.
    model_name : str, optional
        Override for the Ollama model name.
    enable_hitl : bool
        If True, the live-session graph compiles with an interrupt before
        the ATC response node so an instructor can override.
    """

    def __init__(
        self,
        ollama_base_url: str | None = None,
        model_name: str | None = None,
        enable_hitl: bool = False,
    ) -> None:
        settings = get_settings()
        llm_settings = settings.llm
        if ollama_base_url or model_name:
            llm_settings = replace(
                llm_settings,
                base_url=ollama_base_url or llm_settings.base_url,
                model=model_name or llm_settings.model,
            )
            settings = settings.model_copy(update={"llm": llm_settings})
        self._base_url = llm_settings.base_url
        self._model = llm_settings.model

        # Build sub-graphs
        self.validation_graph = build_validation_graph()
        self.live_session_graph = build_live_session_graph(
            build_llm(settings),
            DEFAULT_SCENE,
            enable_hitl,
        )
        self.scoring_graph = build_scoring_graph()

        # In-memory session store — swap for Redis in production
        self._sessions: dict[str, HorusState] = {}

        logger.info(
            "HorusOrchestrator initialized (model=%s, HITL=%s)",
            self._model,
            enable_hitl,
        )

    # ── Session lifecycle ─────────────────────────────────────────

    async def start_session(
        self,
        flight_plan_data: dict[str, Any],
        user_id: str | None = None,
        language: str = "en",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ingest a flight plan, run validation, and prepare the session.

        Args:
            flight_plan_data: Dict matching ``FlightPlanState`` keys.
            user_id: Authenticated user ID (optional for MVP).
            language: UI / response language (``en`` or ``es``).
            context: Additional flight context (callsign, etc.).

        Returns:
            Dict with ``session_id``, ``validation_passed``,
            ``validation_results``, ``weather``, ``fuel_state``,
            ``route_info``, ``airspace_info``, ``aircraft_performance``,
            and ``phase``.
        """
        session_id = str(uuid.uuid4())

        initial_state: HorusState = {
            "messages": [],
            "session_id": session_id,
            "user_id": user_id,
            "phase": SessionPhase.INGESTION.value,
            "flight_plan": flight_plan_data,
            "weather": None,
            "fuel_state": None,
            "route_info": None,
            "airspace_info": None,
            "aircraft_performance": None,
            "validation_results": [],
            "validation_passed": False,
            "pilot_message": None,
            "atc_response": None,
            "exchange_count": 0,
            "current_waypoint_index": 0,
            "session_phase_detail": "briefing",
            "performance_notes": [],
            "is_emergency": False,
            "scoring": None,
            "badges_earned": [],
            "language": language,
            "context": context or {},
        }

        logger.info("Starting session %s — running validation", session_id)
        result = await self.validation_graph.ainvoke(initial_state)

        # Persist state
        self._sessions[session_id] = result

        return {
            "session_id": session_id,
            "validation_passed": result.get("validation_passed", False),
            "validation_results": result.get("validation_results", []),
            "weather": result.get("weather"),
            "fuel_state": result.get("fuel_state"),
            "route_info": result.get("route_info"),
            "airspace_info": result.get("airspace_info"),
            "aircraft_performance": result.get("aircraft_performance"),
            "phase": result.get("phase", SessionPhase.VALIDATION.value),
        }

    async def process_message(
        self,
        session_id: str,
        pilot_message: str,
        context_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a single pilot transmission in a live session.

        Args:
            session_id: Active session identifier.
            pilot_message: Transcribed pilot radio call.
            context_overrides: Optional dict to merge into context
                (e.g. updated altitude, position).

        Returns:
            Dict with ``atc_response``, ``is_emergency``,
            ``exchange_count``, ``performance_notes``, ``phase``.

        Raises:
            KeyError: If ``session_id`` is not found.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")

        state = self._sessions[session_id]

        # Update state for this exchange
        state["pilot_message"] = pilot_message
        state["phase"] = SessionPhase.ACTIVE.value
        if context_overrides:
            state["context"] = {**(state.get("context") or {}), **context_overrides}

        logger.info(
            "Session %s — processing message #%d",
            session_id,
            state.get("exchange_count", 0) + 1,
        )
        result = await self.live_session_graph.ainvoke(state)

        # Persist updated state
        self._sessions[session_id] = result

        return {
            "atc_response": result.get("atc_response", ""),
            "is_emergency": result.get("is_emergency", False),
            "exchange_count": result.get("exchange_count", 0),
            "performance_notes": result.get("performance_notes", []),
            "session_phase_detail": result.get("session_phase_detail", ""),
            "phase": result.get("phase", SessionPhase.ACTIVE.value),
        }

    async def end_session(
        self,
        session_id: str,
        student_stats_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """End the session and run post-flight scoring.

        Args:
            session_id: Active session identifier.
            student_stats_context: Cumulative student stats for badge
                evaluation (total_sessions, total_flight_hours,
                current_streak, etc.).

        Returns:
            Dict with ``scoring``, ``badges_earned``, ``report``,
            ``phase``.

        Raises:
            KeyError: If ``session_id`` is not found.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")

        state = self._sessions[session_id]
        state["phase"] = SessionPhase.POST_FLIGHT.value

        # Merge cumulative stats into context for badge evaluation
        if student_stats_context:
            state["context"] = {
                **(state.get("context") or {}),
                **student_stats_context,
            }

        logger.info("Session %s — running post-flight scoring", session_id)
        result = await self.scoring_graph.ainvoke(state)

        # Persist final state
        self._sessions[session_id] = result

        report = (result.get("context") or {}).get("report", "")

        return {
            "scoring": result.get("scoring"),
            "badges_earned": result.get("badges_earned", []),
            "report": report,
            "phase": result.get("phase", SessionPhase.COMPLETE.value),
        }

    # ── Session management helpers ────────────────────────────────

    def get_session_state(self, session_id: str) -> HorusState | None:
        """Retrieve the current state for a session."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from the in-memory store."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Session %s deleted", session_id)
            return True
        return False
