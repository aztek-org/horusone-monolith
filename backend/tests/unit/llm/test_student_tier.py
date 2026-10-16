"""Unit tests for the heuristic student-performance scoring agent."""

from __future__ import annotations

import pytest

from app.services.llm.agents import student_tier
from app.services.llm.agents.student_tier import (
    _determine_grade,
    _score_communication,
    _score_decisions,
    _score_procedures,
    _score_timing,
    evaluate_student,
)


class TestScoreTiming:
    @pytest.mark.parametrize(
        ("exchange_count", "expected"),
        [(0, 30.0), (1, 60.0), (2, 60.0), (3, 75.0), (7, 75.0), (8, 85.0), (14, 85.0), (15, 95.0), (100, 95.0)],
    )
    def test_timing_tiers(self, exchange_count: int, expected: float) -> None:
        assert _score_timing(exchange_count) == expected


class TestDetermineGrade:
    @pytest.mark.parametrize(
        ("score", "grade"),
        [(100.0, "A"), (90.0, "A"), (89.9, "B"), (80.0, "B"), (79.9, "C"), (70.0, "C"), (69.9, "D"), (60.0, "D"), (59.9, "F"), (0.0, "F")],
    )
    def test_grade_thresholds(self, score: float, grade: str) -> None:
        assert _determine_grade(score) == grade


class TestScoreCommunication:
    def test_no_exchanges_gets_a_neutral_score(self) -> None:
        assert _score_communication([], 0) == 50.0

    def test_no_notes_gets_the_seventy_point_baseline(self) -> None:
        assert _score_communication([], 5) == 70.0

    def test_phraseology_errors_are_penalised(self) -> None:
        assert _score_communication(["Phraseology error detected"], 5) == 60.0

    def test_positives_and_emergencies_are_rewarded(self) -> None:
        notes = [
            "Student correctly declared emergency — positive training point",
            "EMERGENCY: mayday detected (urgency: emergency)",
        ]

        # +5 for "correct", +10 for the emergency note, from a base of 70.
        assert _score_communication(notes, 5) == 85.0

    def test_score_is_clamped_to_one_hundred(self) -> None:
        assert _score_communication(["correct"] * 20, 5) == 100.0

    def test_score_is_clamped_at_zero(self) -> None:
        assert _score_communication(["Phraseology error"] * 20, 5) == 0.0


class TestScoreDecisions:
    def test_baseline_without_emergency(self) -> None:
        assert _score_decisions([], False) == 75.0

    def test_emergency_bonus(self) -> None:
        assert _score_decisions([], True) == 90.0

    def test_warnings_and_missed_items_deduct(self) -> None:
        assert _score_decisions(["warning: low altitude", "missed readback"], False) == 59.0


class TestScoreProcedures:
    def test_no_exchanges_gets_a_neutral_score(self) -> None:
        assert _score_procedures([], 0) == 50.0

    def test_clean_session_baseline(self) -> None:
        assert _score_procedures([], 5) == 75.0

    def test_incorrect_readback_deducts_but_also_matches_correct(self) -> None:
        # "incorrect" contains "correct", so both branches fire: -12 then +5.
        assert _score_procedures(["Readback incorrect"], 5) == 68.0

    def test_correct_readback_adds_points(self) -> None:
        assert _score_procedures(["Readback correct"], 5) == 80.0


def test_empty_session_is_a_failing_grade() -> None:
    result = evaluate_student({"performance_notes": [], "exchange_count": 0})
    scoring = result["scoring"]

    assert scoring["communication_score"] == 50.0
    assert scoring["decision_score"] == 75.0
    assert scoring["procedure_score"] == 50.0
    assert scoring["timing_score"] == 30.0
    assert scoring["overall_score"] == pytest.approx(53.2, abs=0.1)
    assert scoring["grade"] == "F"
    assert scoring["strengths"] == [
        "Completed the training session — every flight is a learning opportunity."
    ]
    assert len(scoring["improvements"]) == 3
    assert "0 exchanges" in scoring["summary"]


def test_strong_emergency_session_earns_an_a() -> None:
    state = {
        "performance_notes": ["Correct readback"] * 13,
        "exchange_count": 10,
        "is_emergency": True,
    }

    scoring = evaluate_student(state)["scoring"]

    assert scoring["communication_score"] == 100.0
    assert scoring["decision_score"] == 90.0
    assert scoring["procedure_score"] == 100.0
    assert scoring["timing_score"] == 85.0
    assert scoring["grade"] == "A"
    assert len(scoring["strengths"]) == 4
    assert scoring["improvements"] == ["Keep maintaining your excellent standards!"]


def test_scoring_uses_documented_weights() -> None:
    # comm 70, decision 75, procedure 75, timing 95 for a 15-exchange clean run.
    scoring = evaluate_student({"exchange_count": 15, "performance_notes": []})["scoring"]

    expected = 70 * 0.35 + 75 * 0.25 + 75 * 0.25 + 95 * 0.15
    assert scoring["overall_score"] == pytest.approx(round(expected, 1), abs=0.1)
    assert scoring["grade"] == "C"


def test_weight_constants_sum_to_one() -> None:
    total = (
        student_tier.WEIGHT_COMMUNICATION
        + student_tier.WEIGHT_DECISION
        + student_tier.WEIGHT_PROCEDURE
        + student_tier.WEIGHT_TIMING
    )
    assert total == pytest.approx(1.0)
