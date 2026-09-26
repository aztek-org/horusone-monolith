"""Thin stateful adapter over the shared live-session ATC graph."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.llm import LLMModule
from app.services.llm.graphs.live_session_graph import build_live_session_graph
from app.services.llm.scenes.registry import SceneConfig
from app.services.llm.state import HorusState, SessionPhase

logger = logging.getLogger(__name__)


@dataclass
class ATCAgent:
    """Adapt one live graph exchange to the existing AudioPipeline interface."""

    llm: LLMModule
    scene: SceneConfig
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    graph: Any = field(init=False)

    def __post_init__(self) -> None:
        """Build the shared live-session graph with injected dependencies."""
        self.graph = build_live_session_graph(
            self.llm,
            self.scene,
            interrupt_before_response=False,
        )
        logger.info("ATC adapter initialized with Scene %s", self.scene.version)

    async def generate_response(
        self,
        pilot_message: str,
        context: dict | None = None,
        language: str = "en",
    ) -> str:
        """Run one pilot-to-ATC exchange and retain its public history."""
        messages: list[dict[str, str]] = []
        for exchange in self.conversation_history[-3:]:
            messages.extend(
                [
                    {"role": "user", "content": exchange["pilot"]},
                    {"role": "assistant", "content": exchange["atc"]},
                ]
            )

        initial_state: HorusState = {
            "messages": messages,
            "pilot_message": pilot_message,
            "atc_response": "",
            "context": context or {},
            "language": language,
            "phase": SessionPhase.ACTIVE.value,
            "session_phase_detail": "briefing",
            "exchange_count": len(self.conversation_history),
            "performance_notes": [],
        }
        result = await self.graph.ainvoke(initial_state)
        atc_response = result.get("atc_response") or ""

        self.conversation_history.append(
            {"pilot": pilot_message, "atc": atc_response, "language": language}
        )
        logger.info("Generated ATC response (%s): %s", language, atc_response)
        return atc_response

    def reset_conversation(self) -> None:
        """Reset the public conversation history."""
        self.conversation_history = []
        logger.info("Conversation history reset")

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Return the public pilot/ATC exchange history."""
        return self.conversation_history
