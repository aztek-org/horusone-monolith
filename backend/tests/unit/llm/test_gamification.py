"""Unit tests for the deterministic gamification badge agent."""

from __future__ import annotations

from typing import Any

from app.services.llm.agents.gamification import BADGE_DEFINITIONS, check_badges


def test_first_session_earns_the_first_flight_badge() -> None:
    result = check_badges({})

    assert result["badges_earned"] == ["first-flight"]


def test_already_earned_badges_are_never_re_awarded() -> None:
    result = check_badges(
        {
            "badges_earned": ["first-flight"],
            "context": {"total_sessions": 1},
        }
    )

    assert result["badges_earned"] == ["first-flight"]


def test_many_badges_are_awarded_in_definition_order() -> None:
    state: dict[str, Any] = {
        "scoring": {
            "communication_score": 96,
            "overall_score": 96,
            "grade": "A",
        },
        "context": {
            "current_streak": 7,
            "total_flight_hours": 50.0,
            "is_night_session": True,
            "a_grade_count": 5,
        },
        "is_emergency": True,
    }

    result = check_badges(state)

    assert result["badges_earned"] == [
        "first-flight",
        "10-hour-pilot",
        "50-hour-pilot",
        "phraseology-master",
        "perfect-session",
        "streak-3",
        "streak-7",
        "emergency-handler",
        "ace-grade",
        "night-owl",
    ]


def test_clear_communicator_requires_consecutive_previous_sessions() -> None:
    earned = check_badges(
        {
            "scoring": {"communication_score": 85},
            "context": {"consecutive_comm_80": 2},
        }
    )["badges_earned"]

    assert "clear-communicator" in earned


def test_clear_communicator_not_awarded_without_history() -> None:
    earned = check_badges(
        {"scoring": {"communication_score": 85}, "context": {}}
    )["badges_earned"]

    assert "clear-communicator" not in earned


def test_emergency_flag_is_added_to_context() -> None:
    earned = check_badges({"is_emergency": True})["badges_earned"]

    assert "emergency-handler" in earned


def test_a_grade_increments_the_ace_counter() -> None:
    # Four prior A grades + this session's A = 5 → Ace.
    earned = check_badges(
        {"scoring": {"grade": "A"}, "context": {"a_grade_count": 4}}
    )["badges_earned"]

    assert "ace-grade" in earned


def test_input_state_is_not_mutated() -> None:
    state: dict[str, Any] = {"context": {"total_sessions": 3}}

    check_badges(state)

    assert state["context"] == {"total_sessions": 3}


def test_all_badge_slugs_are_unique() -> None:
    slugs = [definition["slug"] for definition in BADGE_DEFINITIONS]

    assert len(slugs) == len(set(slugs))
