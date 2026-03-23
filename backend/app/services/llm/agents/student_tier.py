"""Student tier agent — post-session performance evaluation.

Scores communication accuracy, decision quality, procedure adherence,
and response timing.  Uses heuristic scoring (no LLM needed for MVP).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.llm.state import HorusState

logger = logging.getLogger(__name__)

# ── Scoring weights ───────────────────────────────────────────────────

WEIGHT_COMMUNICATION = 0.35
WEIGHT_DECISION = 0.25
WEIGHT_PROCEDURE = 0.25
WEIGHT_TIMING = 0.15

# ── ICAO phraseology patterns (positive indicators) ──────────────────

GOOD_PHRASEOLOGY = [
    r"\b(roger|wilco|affirm|negative|say again|read back|correction)\b",
    r"\bcleared\b",
    r"\b(runway|flight level|squawk|altimeter)\b",
    r"\b(maintain|descend|climb|turn|heading|direct)\b",
    r"\b(contact|monitor)\s+\w+\s+(on|frequency)\b",
    r"\b\d{3}\s+at\s+\d+\b",  # wind reporting: "280 at 10"
]

# ── Bad phraseology patterns (negative indicators) ────────────────────

BAD_PHRASEOLOGY = [
    r"\bover and out\b",
    r"\bplease\b",
    r"\bthank you\b",
    r"\buh+\b",
    r"\bum+\b",
    r"\byeah\b",
    r"\bokay\b",
    r"\bsure\b",
    r"\b(hi|hello|hey)\b",
]

# ── Grade thresholds ──────────────────────────────────────────────────

GRADE_THRESHOLDS = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "F"),
]


def _score_communication(performance_notes: list[str], exchange_count: int) -> float:
    """Score communication quality from performance notes.

    Looks for phraseology errors and compliments recorded by the
    understand/evaluate nodes during the live session.
    """
    if exchange_count == 0:
        return 50.0

    errors = sum(1 for n in performance_notes if "Phraseology" in n or "error" in n.lower())
    positives = sum(1 for n in performance_notes if "correct" in n.lower() or "good" in n.lower())
    emergencies = sum(1 for n in performance_notes if "EMERGENCY" in n)

    # Base score 70, +5 per positive, -10 per error, +10 per emergency handled
    score = 70.0 + (positives * 5.0) - (errors * 10.0) + (emergencies * 10.0)
    return max(0.0, min(100.0, score))


def _score_decisions(performance_notes: list[str], is_emergency: bool) -> float:
    """Score decision quality."""
    base = 75.0

    # Emergency declaration is good decision-making
    if is_emergency:
        base += 15.0

    # Deductions for noted issues
    issues = sum(1 for n in performance_notes if "warning" in n.lower() or "missed" in n.lower())
    base -= issues * 8.0

    return max(0.0, min(100.0, base))


def _score_procedures(performance_notes: list[str], exchange_count: int) -> float:
    """Score procedure adherence."""
    if exchange_count == 0:
        return 50.0

    base = 75.0

    # Readback errors
    readback_errors = sum(1 for n in performance_notes if "readback" in n.lower() and "incorrect" in n.lower())
    base -= readback_errors * 12.0

    # Correct readbacks
    readback_ok = sum(1 for n in performance_notes if "readback" in n.lower() and "correct" in n.lower())
    base += readback_ok * 5.0

    return max(0.0, min(100.0, base))


def _score_timing(exchange_count: int) -> float:
    """Score response timing (more exchanges = more practice = better)."""
    if exchange_count == 0:
        return 30.0
    if exchange_count < 3:
        return 60.0
    if exchange_count < 8:
        return 75.0
    if exchange_count < 15:
        return 85.0
    return 95.0


def _determine_grade(score: float) -> str:
    """Map an overall score to a letter grade."""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _generate_strengths_and_improvements(
    comm_score: float,
    decision_score: float,
    procedure_score: float,
    timing_score: float,
) -> tuple[list[str], list[str]]:
    """Generate human-readable strength and improvement lists."""
    strengths: list[str] = []
    improvements: list[str] = []

    # Communication
    if comm_score >= 80:
        strengths.append("Strong use of standard ICAO phraseology.")
    elif comm_score < 60:
        improvements.append("Practice standard ICAO phraseology — avoid informal language.")

    # Decisions
    if decision_score >= 80:
        strengths.append("Good situational awareness and decision-making.")
    elif decision_score < 60:
        improvements.append("Work on decision-making — consider all options before responding.")

    # Procedures
    if procedure_score >= 80:
        strengths.append("Correct readback procedures observed.")
    elif procedure_score < 60:
        improvements.append("Always read back clearances, altimeter settings, and runway assignments.")

    # Timing
    if timing_score >= 80:
        strengths.append("Good session engagement with adequate practice volume.")
    elif timing_score < 60:
        improvements.append("Spend more time practicing — longer sessions improve retention.")

    if not strengths:
        strengths.append("Completed the training session — every flight is a learning opportunity.")
    if not improvements:
        improvements.append("Keep maintaining your excellent standards!")

    return strengths, improvements


def evaluate_student(state: HorusState) -> dict[str, Any]:
    """Evaluate student performance for the completed session.

    Returns:
        Partial state update with ``scoring``.
    """
    performance_notes = state.get("performance_notes") or []
    exchange_count = state.get("exchange_count", 0)
    is_emergency = state.get("is_emergency", False)

    comm_score = _score_communication(performance_notes, exchange_count)
    decision_score = _score_decisions(performance_notes, is_emergency)
    procedure_score = _score_procedures(performance_notes, exchange_count)
    timing_score = _score_timing(exchange_count)

    overall = (
        comm_score * WEIGHT_COMMUNICATION
        + decision_score * WEIGHT_DECISION
        + procedure_score * WEIGHT_PROCEDURE
        + timing_score * WEIGHT_TIMING
    )

    grade = _determine_grade(overall)
    strengths, improvements = _generate_strengths_and_improvements(
        comm_score, decision_score, procedure_score, timing_score
    )

    summary = (
        f"Session completed with {exchange_count} exchanges. "
        f"Overall grade: {grade} ({overall:.0f}/100). "
        f"Communication: {comm_score:.0f}, Decisions: {decision_score:.0f}, "
        f"Procedures: {procedure_score:.0f}, Engagement: {timing_score:.0f}."
    )

    scoring = {
        "communication_score": round(comm_score, 1),
        "decision_score": round(decision_score, 1),
        "procedure_score": round(procedure_score, 1),
        "timing_score": round(timing_score, 1),
        "overall_score": round(overall, 1),
        "grade": grade,
        "strengths": strengths,
        "improvements": improvements,
        "summary": summary,
    }

    logger.info(
        "Student evaluation: overall=%.0f (%s), comm=%.0f, dec=%.0f, proc=%.0f, time=%.0f",
        overall,
        grade,
        comm_score,
        decision_score,
        procedure_score,
        timing_score,
    )

    return {"scoring": scoring}
