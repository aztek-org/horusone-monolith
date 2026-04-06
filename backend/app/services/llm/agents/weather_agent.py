"""Weather agent — METAR/TAF fetch, hazard analysis, LLM briefing.

Fetches weather data for departure, arrival, and alternate airports,
determines the flight category, identifies hazards, and optionally
generates a natural-language weather briefing via the LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, Severity, SessionPhase
from app.services.llm.tools.weather_tools import (
    fetch_metar,
    fetch_taf,
    parse_metar,
)

logger = logging.getLogger(__name__)

# Keywords in raw METAR/TAF that indicate hazards
HAZARD_KEYWORDS: dict[str, str] = {
    "TS": "Thunderstorm",
    "+RA": "Heavy rain",
    "FG": "Fog",
    "FZRA": "Freezing rain",
    "SN": "Snow",
    "+SN": "Heavy snow",
    "BR": "Mist (visibility reduced)",
    "FU": "Smoke",
    "GR": "Hail",
    "IC": "Ice crystals",
    "LLWS": "Low-level wind shear",
    "CB": "Cumulonimbus",
    "TCU": "Towering cumulus",
}


def _extract_hazards(raw_metar: str, raw_taf: str) -> list[str]:
    """Scan raw METAR and TAF for weather hazard keywords."""
    hazards: list[str] = []
    combined = f"{raw_metar} {raw_taf}".upper()
    for code, label in HAZARD_KEYWORDS.items():
        if code in combined:
            hazards.append(f"{label} ({code})")
    return hazards


def _generate_recommendations(
    flight_category: str,
    hazards: list[str],
    flight_rules: str,
) -> list[str]:
    """Generate actionable recommendations based on weather analysis."""
    recs: list[str] = []

    if flight_category in ("IFR", "LIFR") and flight_rules == "VFR":
        recs.append(
            "CRITICAL: Conditions are below VFR minimums. "
            "Do not depart under VFR flight rules."
        )
    elif flight_category == "MVFR" and flight_rules == "VFR":
        recs.append(
            "Conditions are marginal VFR. Exercise caution and have a "
            "diversion plan. Consider postponing if ceilings deteriorate."
        )

    for h in hazards:
        if "Thunderstorm" in h:
            recs.append("Thunderstorms reported — avoid area, expect holds or reroutes.")
        if "Freezing rain" in h or "Ice" in h:
            recs.append("Icing conditions — verify aircraft is equipped and approved for icing.")
        if "Wind shear" in h:
            recs.append("Low-level wind shear reported — be prepared for go-around.")
        if "Fog" in h or "Mist" in h:
            recs.append("Reduced visibility due to fog/mist — confirm approach minimums.")

    if not recs:
        recs.append("Weather conditions are acceptable for the planned flight.")

    return recs


def analyze_weather(state: HorusState) -> dict[str, Any]:
    """Fetch and analyse weather for all flight plan airports.

    Returns:
        Partial state update with ``weather`` and appended ``validation_results``.
    """
    results: list[dict[str, Any]] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan") or {}

    dep_icao = flight_plan.get("departure_icao", "")
    arr_icao = flight_plan.get("arrival_icao", "")
    alt_icao = flight_plan.get("alternate_icao") or ""
    flight_rules = flight_plan.get("flight_rules", "VFR").upper()

    # Fetch raw weather data
    dep_metar_raw = fetch_metar(dep_icao) if dep_icao else ""
    arr_metar_raw = fetch_metar(arr_icao) if arr_icao else ""
    alt_metar_raw = fetch_metar(alt_icao) if alt_icao else ""
    dep_taf_raw = fetch_taf(dep_icao) if dep_icao else ""
    arr_taf_raw = fetch_taf(arr_icao) if arr_icao else ""

    # Parse departure and arrival METARs
    dep_parsed = parse_metar(dep_metar_raw) if dep_metar_raw else {}
    arr_parsed = parse_metar(arr_metar_raw) if arr_metar_raw else {}

    # Determine worst-case flight category
    dep_cat = dep_parsed.get("flight_category", "VFR")
    arr_cat = arr_parsed.get("flight_category", "VFR")
    category_priority = {"LIFR": 0, "IFR": 1, "MVFR": 2, "VFR": 3}
    worst_cat = dep_cat if category_priority.get(dep_cat, 3) < category_priority.get(arr_cat, 3) else arr_cat

    # Hazards
    hazards = _extract_hazards(
        f"{dep_metar_raw} {arr_metar_raw}",
        f"{dep_taf_raw} {arr_taf_raw}",
    )

    # Recommendations
    recommendations = _generate_recommendations(worst_cat, hazards, flight_rules)

    # Build briefing text (deterministic, no LLM needed for MVP)
    briefing_lines = [
        f"Departure ({dep_icao}): {dep_metar_raw}",
        f"  Flight category: {dep_cat}",
        f"Arrival ({arr_icao}): {arr_metar_raw}",
        f"  Flight category: {arr_cat}",
    ]
    if alt_icao:
        briefing_lines.append(f"Alternate ({alt_icao}): {alt_metar_raw}")
    if hazards:
        briefing_lines.append(f"Hazards: {', '.join(hazards)}")
    briefing_lines.append(f"Recommendations: {' '.join(recommendations)}")
    briefing_text = "\n".join(briefing_lines)

    # Validation results
    if worst_cat in ("IFR", "LIFR") and flight_rules == "VFR":
        results.append({
            "agent": "weather",
            "passed": False,
            "severity": Severity.CRITICAL.value,
            "message": (
                f"Weather is {worst_cat} — below VFR minimums. "
                "Flight cannot proceed under VFR."
            ),
            "details": {
                "departure_category": dep_cat,
                "arrival_category": arr_cat,
            },
        })
    elif worst_cat == "MVFR" and flight_rules == "VFR":
        results.append({
            "agent": "weather",
            "passed": True,
            "severity": Severity.WARNING.value,
            "message": "Marginal VFR conditions — proceed with caution.",
            "details": {
                "departure_category": dep_cat,
                "arrival_category": arr_cat,
            },
        })
    else:
        results.append({
            "agent": "weather",
            "passed": True,
            "severity": Severity.INFO.value,
            "message": f"Weather analysis complete — {worst_cat} conditions.",
            "details": {
                "departure_category": dep_cat,
                "arrival_category": arr_cat,
            },
        })

    if hazards:
        results.append({
            "agent": "weather",
            "passed": True,
            "severity": Severity.WARNING.value,
            "message": f"Weather hazards detected: {', '.join(hazards)}.",
            "details": {"hazards": hazards},
        })

    weather_state = {
        "departure_metar": dep_metar_raw,
        "arrival_metar": arr_metar_raw,
        "alternate_metar": alt_metar_raw or None,
        "departure_taf": dep_taf_raw,
        "arrival_taf": arr_taf_raw,
        "flight_category": worst_cat,
        "hazards": hazards,
        "recommendations": recommendations,
        "briefing_text": briefing_text,
    }

    logger.info("Weather agent: %s conditions, %d hazards", worst_cat, len(hazards))

    return {
        "weather": weather_state,
        "validation_results": results,
    }
