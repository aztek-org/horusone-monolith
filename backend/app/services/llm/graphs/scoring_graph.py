"""Scoring graph — post-session evaluation and badge award pipeline.

```mermaid
graph TD
    START([START]) --> student_eval["student_tier.evaluate_student"]
    student_eval --> badge_check["gamification.check_badges"]
    badge_check --> generate_report["generate_report"]
    generate_report --> END([END])
```

Runs after a live session ends.  Produces a ``ScoringResult`` and
a list of newly-earned badge slugs.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.services.llm.agents.gamification import check_badges
from app.services.llm.agents.student_tier import evaluate_student
from app.services.llm.state import HorusState, SessionPhase

logger = logging.getLogger(__name__)


def _generate_report(state: HorusState) -> dict[str, Any]:
    """Compile a final session report from scoring + badges.

    This node assembles the human-readable summary that gets returned
    to the frontend and (optionally) persisted as a ``FlightInsight``.
    """
    scoring = state.get("scoring") or {}
    badges = state.get("badges_earned") or []
    exchange_count = state.get("exchange_count", 0)
    context = state.get("context") or {}
    callsign = context.get("callsign", "Student")
    performance_notes = state.get("performance_notes") or []

    # Build report sections
    report_lines: list[str] = [
        "═══════════════════════════════════════════",
        f"  HORUS POST-FLIGHT REPORT — {callsign}",
        "═══════════════════════════════════════════",
        "",
        f"Overall Grade: {scoring.get('grade', 'N/A')} ({scoring.get('overall_score', 0):.0f}/100)",
        "",
        "── Scores ──────────────────────────────────",
        f"  Communication:  {scoring.get('communication_score', 0):.0f}/100",
        f"  Decisions:      {scoring.get('decision_score', 0):.0f}/100",
        f"  Procedures:     {scoring.get('procedure_score', 0):.0f}/100",
        f"  Engagement:     {scoring.get('timing_score', 0):.0f}/100",
        "",
        f"  Exchanges:      {exchange_count}",
        "",
    ]

    strengths = scoring.get("strengths") or []
    improvements = scoring.get("improvements") or []

    if strengths:
        report_lines.append("── Strengths ───────────────────────────────")
        for s in strengths:
            report_lines.append(f"  ✅ {s}")
        report_lines.append("")

    if improvements:
        report_lines.append("── Areas for Improvement ───────────────────")
        for imp in improvements:
            report_lines.append(f"  📝 {imp}")
        report_lines.append("")

    if badges:
        report_lines.append("── Badges Earned ───────────────────────────")
        for badge_slug in badges:
            report_lines.append(f"  🏅 {badge_slug}")
        report_lines.append("")

    if performance_notes:
        report_lines.append("── Session Notes ───────────────────────────")
        for note in performance_notes[-10:]:  # Limit to last 10
            report_lines.append(f"  • {note}")
        report_lines.append("")

    report_lines.append("═══════════════════════════════════════════")

    report_text = "\n".join(report_lines)

    logger.info("Post-flight report generated for %s", callsign)

    return {
        "phase": SessionPhase.COMPLETE.value,
        "context": {
            **context,
            "report": report_text,
        },
    }


def build_scoring_graph() -> StateGraph:
    """Build and compile the scoring sub-graph.

    Returns:
        Compiled LangGraph ``StateGraph`` ready for ``.ainvoke()``.
    """
    graph = StateGraph(HorusState)

    # ── Nodes ─────────────────────────────────────────────────────
    graph.add_node("student_eval", evaluate_student)
    graph.add_node("badge_check", check_badges)
    graph.add_node("generate_report", _generate_report)

    # ── Edges ─────────────────────────────────────────────────────
    graph.set_entry_point("student_eval")
    graph.add_edge("student_eval", "badge_check")
    graph.add_edge("badge_check", "generate_report")
    graph.add_edge("generate_report", END)

    compiled = graph.compile()
    logger.info("Scoring graph compiled (3 nodes)")
    return compiled
