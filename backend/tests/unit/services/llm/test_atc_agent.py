"""Unit tests for the LangGraph-based ATC agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm.atc_agent import ATCAgent, AgentState, SessionPhase


# ── Helpers ────────────────────────────────────────────────────────────


def _make_agent() -> ATCAgent:
    """Create an ATCAgent with mocked LLM and settings."""
    with (
        patch("app.services.llm.atc_agent.get_settings") as mock_settings,
        patch("app.services.llm.atc_agent.Ollama") as mock_ollama,
    ):
        settings = MagicMock()
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_llm_model = "test-model"
        mock_settings.return_value = settings
        mock_ollama.return_value = MagicMock()

        agent = ATCAgent()
    return agent


def _make_state(
    *,
    pilot_message: str = "Requesting clearance",
    performance_notes: list[str] | None = None,
    context: dict | None = None,
    language: str = "en",
    session_phase: str = SessionPhase.ACTIVE.value,
    exchange_count: int = 0,
) -> AgentState:
    return AgentState(
        messages=[],
        pilot_message=pilot_message,
        atc_response="",
        context=context or {},
        language=language,
        session_phase=session_phase,
        exchange_count=exchange_count,
        performance_notes=performance_notes or [],
    )


# ── _clean_response ───────────────────────────────────────────────────


class TestCleanResponse:
    """Tests for ATCAgent._clean_response()."""

    def test_remove_atc_prefix(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("ATC: Cleared for takeoff runway 27.")
        assert result == "Cleared for takeoff runway 27."

    def test_remove_tower_prefix(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Tower: Contact approach on 123.4.")
        assert result == "Contact approach on 123.4."

    def test_remove_approach_prefix(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Approach: Descend and maintain flight level 250.")
        assert result == "Descend and maintain flight level 250."

    def test_remove_ground_prefix(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Ground: Taxi to runway 27 via Alpha.")
        assert result == "Taxi to runway 27 via Alpha."

    def test_remove_response_prefix(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Response: Roger, maintain heading 270.")
        assert result == "Roger, maintain heading 270."

    def test_no_prefix_unchanged(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Cleared for takeoff runway 27.")
        assert result == "Cleared for takeoff runway 27."

    def test_whitespace_normalization(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("  Cleared   for   takeoff  runway  27.  ")
        assert result == "Cleared for takeoff runway 27."

    def test_multiline_collapsed(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("Line one\n  line two\n  line three")
        assert result == "Line one line two line three"

    def test_empty_string(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("")
        assert result == ""

    def test_prefix_only(self) -> None:
        agent = _make_agent()
        result = agent._clean_response("ATC:")
        assert result == ""


# ── _understand_node ──────────────────────────────────────────────────


class TestUnderstandNode:
    """Tests for the understand node — keyword-based classification."""

    @pytest.mark.asyncio
    async def test_mayday_detected(self) -> None:
        agent = _make_agent()
        state = _make_state(pilot_message="MAYDAY MAYDAY MAYDAY engine failure")
        result = await agent._understand_node(state)
        assert any("EMERGENCY" in n for n in result["performance_notes"])

    @pytest.mark.asyncio
    async def test_pan_pan_detected(self) -> None:
        agent = _make_agent()
        state = _make_state(pilot_message="Pan pan, passenger medical issue")
        result = await agent._understand_node(state)
        assert any("EMERGENCY" in n for n in result["performance_notes"])

    @pytest.mark.asyncio
    async def test_emergency_keyword_detected(self) -> None:
        agent = _make_agent()
        state = _make_state(pilot_message="We have an emergency, low fuel")
        result = await agent._understand_node(state)
        assert any("EMERGENCY" in n for n in result["performance_notes"])

    @pytest.mark.asyncio
    async def test_declare_keyword_detected(self) -> None:
        agent = _make_agent()
        state = _make_state(pilot_message="We declare fuel emergency")
        result = await agent._understand_node(state)
        assert any("EMERGENCY" in n for n in result["performance_notes"])

    @pytest.mark.asyncio
    async def test_over_and_out_phraseology_error(self) -> None:
        agent = _make_agent()
        state = _make_state(
            pilot_message="Roger wilco, over and out"
        )
        result = await agent._understand_node(state)
        assert any("over and out" in n for n in result["performance_notes"])

    @pytest.mark.asyncio
    async def test_normal_message_no_notes(self) -> None:
        agent = _make_agent()
        state = _make_state(
            pilot_message="Tower, Cessna 1234 Alpha, ready for takeoff runway 27"
        )
        result = await agent._understand_node(state)
        assert result["performance_notes"] == []

    @pytest.mark.asyncio
    async def test_preserves_existing_performance_notes(self) -> None:
        agent = _make_agent()
        state = _make_state(
            pilot_message="MAYDAY fuel emergency",
            performance_notes=["Prior note"],
        )
        result = await agent._understand_node(state)
        assert "Prior note" in result["performance_notes"]
        assert any("EMERGENCY" in n for n in result["performance_notes"])


# ── _evaluate_node ────────────────────────────────────────────────────


class TestEvaluateNode:
    """Tests for the evaluate node — exchange tracking and phase progression."""

    @pytest.mark.asyncio
    async def test_increments_exchange_count(self) -> None:
        agent = _make_agent()
        state = _make_state(exchange_count=3)
        result = await agent._evaluate_node(state)
        assert result["exchange_count"] == 4

    @pytest.mark.asyncio
    async def test_briefing_advances_to_active(self) -> None:
        agent = _make_agent()
        state = _make_state(
            session_phase=SessionPhase.BRIEFING.value,
            exchange_count=0,
        )
        result = await agent._evaluate_node(state)
        assert result["session_phase"] == SessionPhase.ACTIVE.value

    @pytest.mark.asyncio
    async def test_active_phase_stays_active(self) -> None:
        agent = _make_agent()
        state = _make_state(
            session_phase=SessionPhase.ACTIVE.value,
            exchange_count=5,
        )
        result = await agent._evaluate_node(state)
        assert result["session_phase"] == SessionPhase.ACTIVE.value


# ── _respond_node ─────────────────────────────────────────────────────


class TestRespondNode:
    """Tests for the respond node — LLM invocation."""

    @pytest.mark.asyncio
    async def test_calls_llm_and_cleans_response(self) -> None:
        agent = _make_agent()
        agent.llm = AsyncMock()
        agent.llm.ainvoke.return_value = "ATC: Cleared for takeoff runway 27."

        state = _make_state(pilot_message="Ready for takeoff")
        result = await agent._respond_node(state)

        assert result["atc_response"] == "Cleared for takeoff runway 27."
        agent.llm.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_error_returns_fallback_en(self) -> None:
        agent = _make_agent()
        agent.llm = AsyncMock()
        agent.llm.ainvoke.side_effect = RuntimeError("Connection refused")

        state = _make_state(pilot_message="Hello tower", language="en")
        result = await agent._respond_node(state)

        assert result["atc_response"] == "Say again, transmission unclear."

    @pytest.mark.asyncio
    async def test_llm_error_returns_fallback_es(self) -> None:
        agent = _make_agent()
        agent.llm = AsyncMock()
        agent.llm.ainvoke.side_effect = RuntimeError("Connection refused")

        state = _make_state(pilot_message="Hola torre", language="es")
        result = await agent._respond_node(state)

        assert result["atc_response"] == "Repita, transmisión no clara."

    @pytest.mark.asyncio
    async def test_includes_conversation_history_in_prompt(self) -> None:
        agent = _make_agent()
        agent.conversation_history = [
            {"pilot": "Ready for pushback", "atc": "Pushback approved"},
        ]
        agent.llm = AsyncMock()
        agent.llm.ainvoke.return_value = "Taxi to runway 27 via Alpha."

        state = _make_state(pilot_message="Ready to taxi")
        result = await agent._respond_node(state)

        # Check the prompt passed to LLM includes history
        call_prompt = agent.llm.ainvoke.call_args[0][0]
        assert "Recent exchanges" in call_prompt
        assert "Ready for pushback" in call_prompt
        assert "Pushback approved" in call_prompt


# ── generate_response ─────────────────────────────────────────────────


class TestGenerateResponse:
    """Tests for the top-level generate_response() method."""

    @pytest.mark.asyncio
    async def test_returns_response_and_updates_history(self) -> None:
        agent = _make_agent()
        # Mock the compiled graph's ainvoke
        agent.graph = AsyncMock()
        agent.graph.ainvoke.return_value = {
            "atc_response": "Cleared for takeoff runway 27.",
        }

        result = await agent.generate_response("Ready for takeoff")

        assert result == "Cleared for takeoff runway 27."
        assert len(agent.conversation_history) == 1
        assert agent.conversation_history[0]["pilot"] == "Ready for takeoff"
        assert agent.conversation_history[0]["atc"] == "Cleared for takeoff runway 27."
        assert agent.conversation_history[0]["language"] == "en"

    @pytest.mark.asyncio
    async def test_custom_language_stored_in_history(self) -> None:
        agent = _make_agent()
        agent.graph = AsyncMock()
        agent.graph.ainvoke.return_value = {
            "atc_response": "Autorizado para despegar pista 27.",
        }

        await agent.generate_response("Listo para despegar", language="es")

        assert agent.conversation_history[0]["language"] == "es"

    @pytest.mark.asyncio
    async def test_context_passed_to_graph(self) -> None:
        agent = _make_agent()
        agent.graph = AsyncMock()
        agent.graph.ainvoke.return_value = {"atc_response": "OK"}

        context = {"callsign": "N1234A", "altitude": "5000"}
        await agent.generate_response("Requesting descent", context=context)

        state_arg = agent.graph.ainvoke.call_args[0][0]
        assert state_arg["context"] == context

    @pytest.mark.asyncio
    async def test_multiple_calls_accumulate_history(self) -> None:
        agent = _make_agent()
        agent.graph = AsyncMock()
        agent.graph.ainvoke.side_effect = [
            {"atc_response": "Response 1"},
            {"atc_response": "Response 2"},
        ]

        await agent.generate_response("Message 1")
        await agent.generate_response("Message 2")

        assert len(agent.conversation_history) == 2
        assert agent.conversation_history[0]["pilot"] == "Message 1"
        assert agent.conversation_history[1]["pilot"] == "Message 2"


# ── reset_conversation / get_conversation_history ─────────────────────


class TestConversationManagement:
    """Tests for history management helpers."""

    def test_reset_clears_history(self) -> None:
        agent = _make_agent()
        agent.conversation_history = [
            {"pilot": "Msg", "atc": "Resp", "language": "en"}
        ]
        agent.reset_conversation()
        assert agent.conversation_history == []

    def test_get_conversation_history_returns_list(self) -> None:
        agent = _make_agent()
        agent.conversation_history = [
            {"pilot": "A", "atc": "B", "language": "en"},
            {"pilot": "C", "atc": "D", "language": "en"},
        ]
        history = agent.get_conversation_history()
        assert len(history) == 2
        assert history[0]["pilot"] == "A"

    def test_get_conversation_history_empty_on_new_agent(self) -> None:
        agent = _make_agent()
        assert agent.get_conversation_history() == []


# ── SessionPhase enum ─────────────────────────────────────────────────


class TestSessionPhase:
    """Tests for the SessionPhase enum values."""

    def test_values(self) -> None:
        assert SessionPhase.BRIEFING.value == "briefing"
        assert SessionPhase.ACTIVE.value == "active"
        assert SessionPhase.DEBRIEFING.value == "debriefing"
        assert SessionPhase.COMPLETE.value == "complete"

    def test_is_string_enum(self) -> None:
        assert isinstance(SessionPhase.ACTIVE, str)
        assert SessionPhase.ACTIVE == "active"
