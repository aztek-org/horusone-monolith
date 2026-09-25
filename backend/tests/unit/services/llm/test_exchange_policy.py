"""The exchange-count and phase-transition policy is defined exactly once.

Both writers of a completed exchange — the live graph's ``evaluate_exchange``
node and the Session module's instructor-release path — used to carry their own
copy of the same two rules.  These tests pin the shared policy in one place and
assert that neither writer can drift from it.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.graphs.live_session_graph import _evaluate_exchange
from app.services.llm.state import advance_exchange
from app.services.training_sessions.session_module import TrainingSessionModule


@pytest.mark.parametrize(
    ("state", "expected_count", "expected_phase_detail"),
    [
        # The first exchange leaves briefing for taxi.  The graph used to guard
        # this with ``exchange_count >= 1`` after pre-incrementing, a condition
        # that can never be false, so the transition is unconditional here.
        ({"exchange_count": 0, "session_phase_detail": "briefing"}, 1, "taxi"),
        ({"exchange_count": 3, "session_phase_detail": "briefing"}, 4, "taxi"),
        # Later phases are preserved rather than re-entered.
        ({"exchange_count": 0, "session_phase_detail": "taxi"}, 1, "taxi"),
        ({"exchange_count": 7, "session_phase_detail": "cruise"}, 8, "cruise"),
        ({"exchange_count": 2, "session_phase_detail": "landing"}, 3, "landing"),
        # Absent keys fall back exactly as each writer did.
        ({"session_phase_detail": "briefing"}, 1, "taxi"),
        ({}, 1, "cruise"),
    ],
)
def test_advance_exchange_counts_the_exchange_and_moves_out_of_briefing(
    state: dict[str, Any],
    expected_count: int,
    expected_phase_detail: str,
) -> None:
    result = advance_exchange(state)

    assert result == {
        "exchange_count": expected_count,
        "session_phase_detail": expected_phase_detail,
        "phase": "active",
    }


def test_live_graph_exchange_node_applies_the_shared_policy() -> None:
    state: dict[str, Any] = {
        "exchange_count": 0,
        "session_phase_detail": "briefing",
        "performance_notes": ["Hesitation detected"],
    }

    result = _evaluate_exchange(state)  # type: ignore[arg-type]

    assert {key: result[key] for key in advance_exchange(state)} == advance_exchange(state)
    assert result["performance_notes"] == ["Hesitation detected"]


def test_instructor_release_applies_the_shared_policy() -> None:
    state: dict[str, Any] = {
        "exchange_count": 1,
        "session_phase_detail": "briefing",
        "atc_response": "Say again, transmission unclear.",
    }

    result = TrainingSessionModule._complete_instructor_exchange(
        state, "Tower, taxi via Alpha."
    )

    assert {key: result[key] for key in advance_exchange(state)} == advance_exchange(state)
    assert result["atc_response"] == "Tower, taxi via Alpha."
    assert result["llm_provider"] == "instructor"
