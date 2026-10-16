"""Prompt construction tests for the prompt templates not owned by a Scene."""

from __future__ import annotations

from app.services.llm import prompts


def test_weather_briefing_prompt_interpolates_flight_context() -> None:
    rendered = prompts.WEATHER_BRIEFING_PROMPT.format(
        departure_icao="KLAX",
        departure_metar="METAR-KLAX",
        departure_taf="TAF-KLAX",
        arrival_icao="KSFO",
        arrival_metar="METAR-KSFO",
        arrival_taf="TAF-KSFO",
        alternate_section="Alternate: KOAK",
        flight_rules="VFR",
        aircraft_type="C172",
    )

    assert "Departure (KLAX)" in rendered
    assert "METAR-KSFO" in rendered
    assert "Alternate: KOAK" in rendered
    assert "Aircraft type: C172" in rendered


def test_emergency_response_prompt_interpolates_position_and_altitude() -> None:
    rendered = prompts.EMERGENCY_RESPONSE_PROMPT.format(
        emergency_type="engine failure",
        callsign="N123AB",
        position="5 NM final",
        altitude=3000,
        nearest_airport="KLAX",
    )

    assert "declared: engine failure" in rendered
    assert "Callsign: N123AB" in rendered
    assert "Altitude: 3000 feet" in rendered


def test_student_evaluation_prompt_interpolates_scores() -> None:
    rendered = prompts.STUDENT_EVALUATION_PROMPT.format(
        exchange_count=12,
        session_phase="cruise",
        callsign="N123AB",
        performance_notes="- handled clearance well",
        communication_score=88,
        decision_score=82,
        procedure_score=91,
    )

    assert "Total exchanges: 12" in rendered
    assert "Communication score: 88/100" in rendered
    assert "Procedure score: 91/100" in rendered


def test_flight_plan_parse_prompt_embeds_free_text() -> None:
    rendered = prompts.FLIGHT_PLAN_PARSE_PROMPT.format(
        free_text="KLAX to KSFO at 3500 feet VFR in a C172"
    )

    assert "KLAX to KSFO at 3500 feet VFR in a C172" in rendered
    assert "ONLY a JSON object" in rendered


def test_readback_evaluation_prompt_embeds_both_statements() -> None:
    rendered = prompts.READBACK_EVALUATION_PROMPT.format(
        atc_clearance="Cleared for takeoff runway 27",
        pilot_readback="Cleared for takeoff runway 27",
        callsign="N123AB",
    )

    assert "Cleared for takeoff runway 27" in rendered
    assert "readback correct" in rendered
