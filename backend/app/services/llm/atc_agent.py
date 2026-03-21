"""LangGraph-based ATC agent with stateful conversation management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, TypedDict

from langchain_community.llms import Ollama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.config import get_settings
from app.services.llm.prompts import get_atc_prompt

logger = logging.getLogger(__name__)


class SessionPhase(str, Enum):
    """Training session phases."""

    BRIEFING = "briefing"
    ACTIVE = "active"
    DEBRIEFING = "debriefing"
    COMPLETE = "complete"


class AgentState(TypedDict):
    """LangGraph state for the ATC agent."""

    messages: Annotated[list, add_messages]
    pilot_message: str
    atc_response: str
    context: dict
    language: str
    session_phase: str
    exchange_count: int
    performance_notes: list[str]


@dataclass
class ATCAgent:
    """Air Traffic Controller agent powered by LangGraph and Ollama.

    Uses a stateful graph to manage conversation flow through:
    understand → respond → evaluate → (loop or end)
    """

    conversation_history: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize the LLM and build the graph."""
        self.settings = get_settings()
        self.llm = Ollama(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_llm_model,
            temperature=0.7,
        )
        self.graph = self._build_graph()
        logger.info(
            "ATC Agent initialized with LangGraph (model: %s)", self.settings.ollama_llm_model
        )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine.

        Graph flow:
            understand → respond → evaluate → END
        """
        builder = StateGraph(AgentState)

        builder.add_node("understand", self._understand_node)
        builder.add_node("respond", self._respond_node)
        builder.add_node("evaluate", self._evaluate_node)

        builder.set_entry_point("understand")
        builder.add_edge("understand", "respond")
        builder.add_edge("respond", "evaluate")
        builder.add_edge("evaluate", END)

        return builder.compile()

    async def _understand_node(self, state: AgentState) -> dict:
        """Classify the pilot's transmission and update context.

        Determines intent (clearance request, position report, emergency, etc.)
        without calling the LLM — uses keyword matching for speed.
        """
        pilot_msg = state["pilot_message"].lower()
        notes = list(state.get("performance_notes", []))

        # Detect emergency keywords
        if any(kw in pilot_msg for kw in ["mayday", "pan pan", "emergency", "declare"]):
            notes.append("EMERGENCY detected — priority handling required")

        # Detect common phraseology errors
        if "over" in pilot_msg and "over and out" in pilot_msg:
            notes.append("Phraseology: 'over and out' is contradictory — note for debrief")

        return {"performance_notes": notes}

    async def _respond_node(self, state: AgentState) -> dict:
        """Generate the ATC response using Ollama."""
        context = state.get("context") or {}
        language = state.get("language", "en")
        pilot_message = state["pilot_message"]

        # Include conversation history for continuity
        history_context = ""
        if self.conversation_history:
            recent = self.conversation_history[-3:]  # Last 3 exchanges
            history_lines = []
            for exc in recent:
                history_lines.append(f"Pilot: {exc['pilot']}")
                history_lines.append(f"ATC: {exc['atc']}")
            history_context = "\nRecent exchanges:\n" + "\n".join(history_lines) + "\n"

        full_prompt = get_atc_prompt(pilot_message, context, language)
        if history_context:
            full_prompt = full_prompt.replace(
                f'"{pilot_message}"',
                f'{history_context}\nCurrent transmission: "{pilot_message}"',
            )

        try:
            response = await self.llm.ainvoke(full_prompt)
            atc_response = self._clean_response(response)
        except Exception as e:
            logger.error("Error generating ATC response: %s", e)
            atc_response = (
                "Repita, transmisión no clara."
                if language == "es"
                else "Say again, transmission unclear."
            )

        return {"atc_response": atc_response}

    async def _evaluate_node(self, state: AgentState) -> dict:
        """Evaluate the exchange and track performance metrics."""
        exchange_count = state.get("exchange_count", 0) + 1
        notes = list(state.get("performance_notes", []))

        # Track exchange for session phase progression
        session_phase = state.get("session_phase", SessionPhase.ACTIVE.value)

        # Auto-progress from briefing to active after first exchange
        if session_phase == SessionPhase.BRIEFING.value and exchange_count >= 1:
            session_phase = SessionPhase.ACTIVE.value

        return {
            "exchange_count": exchange_count,
            "session_phase": session_phase,
            "performance_notes": notes,
        }

    async def generate_response(
        self,
        pilot_message: str,
        context: dict | None = None,
        language: str = "en",
    ) -> str:
        """Generate an ATC response to a pilot transmission.

        Args:
            pilot_message: The transcribed pilot message.
            context: Optional flight context information.
            language: Language code (en or es).

        Returns:
            ATC response text.
        """
        initial_state: AgentState = {
            "messages": [],
            "pilot_message": pilot_message,
            "atc_response": "",
            "context": context or {},
            "language": language,
            "session_phase": SessionPhase.ACTIVE.value,
            "exchange_count": len(self.conversation_history),
            "performance_notes": [],
        }

        result = await self.graph.ainvoke(initial_state)
        atc_response = result["atc_response"]

        self.conversation_history.append(
            {
                "pilot": pilot_message,
                "atc": atc_response,
                "language": language,
            }
        )

        logger.info("Generated ATC response (%s): %s", language, atc_response)
        return atc_response

    def _clean_response(self, response: str) -> str:
        """Clean and format the ATC response.

        Args:
            response: Raw LLM response.

        Returns:
            Cleaned response text.
        """
        cleaned = " ".join(response.strip().split())

        prefixes_to_remove = ["ATC:", "Tower:", "Approach:", "Ground:", "Response:"]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()

        return cleaned

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history reset")

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history.

        Returns:
            List of conversation exchanges.
        """
        return self.conversation_history
