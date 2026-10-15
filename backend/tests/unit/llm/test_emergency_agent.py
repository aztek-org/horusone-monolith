"""Unit tests for the deterministic emergency detection/response agent."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm.agents.emergency_agent import (
    _classify_emergency,
    detect_emergency,
    handle_emergency,
)
from app.services.llm.state import Urgency


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("MAYDAY MAYDAY engine failure", True),
        ("Pan pan, pan pan", True),
        ("I have smoke in cockpit", True),
        ("squawk 7700", True),
        ("requesting taxi clearance", False),
        ("thanks, have a good day", False),
        ("", False),
    ],
)
def test_detect_emergency(message: str, expected: bool) -> None:
    assert detect_emergency(message) is expected


@pytest.mark.parametrize(
    ("message", "expected_type", "expected_urgency"),
    [
        ("mayday mayday", "mayday", Urgency.EMERGENCY.value),
        ("mayday engine failure", "engine_failure", Urgency.EMERGENCY.value),
        ("mayday we have a fire", "fire", Urgency.EMERGENCY.value),
        ("mayday low on fuel", "fuel_emergency", Urgency.EMERGENCY.value),
        ("mayday medical emergency", "medical", Urgency.EMERGENCY.value),
        ("pan pan request descent", "pan_pan", Urgency.PRIORITY.value),
        ("pan pan medical", "medical", Urgency.PRIORITY.value),
        ("squawk 7700", "squawk_7700", Urgency.EMERGENCY.value),
        ("squawk 7600", "squawk_7600", Urgency.EMERGENCY.value),
        ("squawk 7500", "squawk_7500", Urgency.EMERGENCY.value),
        ("engine failure", "engine_failure", Urgency.EMERGENCY.value),
        ("we have a fire", "fire", Urgency.EMERGENCY.value),
        ("smoke in cockpit", "fire", Urgency.EMERGENCY.value),
        ("fuel emergency", "fuel_emergency", Urgency.EMERGENCY.value),
        ("medical emergency", "medical", Urgency.PRIORITY.value),
        ("emergency", "generic", Urgency.EMERGENCY.value),
    ],
)
def test_classify_emergency(
    message: str, expected_type: str, expected_urgency: str
) -> None:
    assert _classify_emergency(message) == (expected_type, expected_urgency)


def _state(message: str, **context: Any) -> dict[str, Any]:
    return {"pilot_message": message, "context": context}


def test_engine_failure_response_uses_context_fields() -> None:
    result = handle_emergency(
        _state(
            "MAYDAY engine failure",
            callsign="N123AB",
            destination="KLAX",
            heading="270",
            altitude="5000",
        )
    )

    assert result["is_emergency"] is True
    assert result["atc_response"] == (
        "N123AB, roger engine failure. Nearest suitable airport is KLAX. "
        "Turn heading 270 for vectors. Say altitude and souls on board."
    )
    assert result["performance_notes"][0].startswith("EMERGENCY: engine_failure")
    assert any("positive training point" in n for n in result["performance_notes"])


def test_missing_context_uses_safe_defaults() -> None:
    result = handle_emergency({"pilot_message": "MAYDAY engine failure"})

    assert result["atc_response"].startswith("Aircraft calling, roger engine failure")
    assert "nearest airport" in result["atc_response"]


def test_pan_pan_response_is_generated() -> None:
    result = handle_emergency(_state("pan pan", callsign="N1"))

    assert result["atc_response"] == (
        "N1, roger PAN PAN. State nature of urgency and assistance required."
    )


def test_generic_emergency_prompts_for_details() -> None:
    result = handle_emergency(_state("declare emergency", callsign="N7"))

    assert result["atc_response"] == (
        "N7, roger emergency. State nature of emergency, souls on board, "
        "and fuel remaining."
    )


def test_existing_performance_notes_are_preserved() -> None:
    result = handle_emergency(
        {
            "pilot_message": "MAYDAY engine failure",
            "performance_notes": ["Hesitation detected"],
        }
    )

    assert result["performance_notes"][0] == "Hesitation detected"
    assert len(result["performance_notes"]) == 3
