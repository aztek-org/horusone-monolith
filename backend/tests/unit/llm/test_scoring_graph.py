"""End-to-end tests for the post-session scoring graph."""

from __future__ import annotations

from typing import Any

from app.services.llm.graphs.scoring_graph import build_scoring_graph


async def test_scoring_graph_produces_scores_badges_and_report() -> None:
    graph = build_scoring_graph()
    state: dict[str, Any] = {
        "messages": [],
        "exchange_count": 15,
        "performance_notes": [],
        "is_emergency": False,
        "context": {"callsign": "N123AB"},
    }

    result = await graph.ainvoke(state)

    assert result["scoring"]["grade"] == "C"
    assert result["scoring"]["overall_score"] == 76.2
    assert result["badges_earned"] == ["first-flight"]
    assert result["phase"] == "complete"
    assert "HORUS POST-FLIGHT REPORT — N123AB" in result["context"]["report"]


async def test_scoring_graph_reports_emergency_handling() -> None:
    graph = build_scoring_graph()
    state: dict[str, Any] = {
        "messages": [],
        "exchange_count": 6,
        "performance_notes": ["EMERGENCY: engine_failure detected (urgency: emergency)"],
        "is_emergency": True,
        "context": {"callsign": "N7"},
    }

    result = await graph.ainvoke(state)

    assert "emergency-handler" in result["badges_earned"]
    assert "N7" in result["context"]["report"]
