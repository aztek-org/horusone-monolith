"""Emergency agent — keyword detection and procedural guidance.

Scans the pilot's transmission for emergency-related keywords and,
when detected, generates appropriate emergency-response ATC instructions.
Can optionally use the LLM for context-aware guidance.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, Urgency

logger = logging.getLogger(__name__)

# ── Emergency keyword sets ────────────────────────────────────────────

MAYDAY_KEYWORDS = {"mayday", "may day"}
PAN_PAN_KEYWORDS = {"pan pan", "pan-pan", "panpan"}
EMERGENCY_KEYWORDS = {
    "declare emergency",
    "emergency",
    "engine failure",
    "engine fire",
    "fire on board",
    "fuel emergency",
    "bingo fuel",
    "smoke in cockpit",
    "bird strike",
    "medical emergency",
    "hijack",
    "squawk 7700",
    "squawk 7600",
    "squawk 7500",
    "lost communication",
    "loss of engine",
    "ditching",
}


# ── Pre-written emergency response templates ──────────────────────────

EMERGENCY_RESPONSES: dict[str, str] = {
    "mayday": (
        "{callsign}, roger MAYDAY. All aircraft on frequency, remain clear. "
        "{callsign}, state souls on board, fuel remaining, and nature of emergency."
    ),
    "pan_pan": (
        "{callsign}, roger PAN PAN. State nature of urgency and assistance required."
    ),
    "engine_failure": (
        "{callsign}, roger engine failure. Nearest suitable airport is {nearest_airport}. "
        "Turn heading {heading} for vectors. Say altitude and souls on board."
    ),
    "fuel_emergency": (
        "{callsign}, roger fuel emergency. You are cleared direct {nearest_airport}. "
        "Expect priority handling. Say fuel remaining in minutes."
    ),
    "fire": (
        "{callsign}, roger fire reported. Cleared direct {nearest_airport}, "
        "descend and maintain {altitude}. Emergency equipment alerted."
    ),
    "squawk_7700": (
        "{callsign}, squawk confirmed 7700. State nature of emergency."
    ),
    "squawk_7600": (
        "{callsign}, if you read, squawk 7600 acknowledged. "
        "Proceed to {nearest_airport} via last assigned route. "
        "Comply with lost communication procedures."
    ),
    "squawk_7500": (
        "{callsign}, squawk 7500 acknowledged."
    ),
    "medical": (
        "{callsign}, roger medical emergency. Closest airport with medical "
        "services is {nearest_airport}. Cleared direct, descend at pilot's discretion. "
        "Emergency services notified."
    ),
    "generic": (
        "{callsign}, roger emergency. State nature of emergency, souls on board, "
        "and fuel remaining."
    ),
}


def _classify_emergency(pilot_message: str) -> tuple[str, str]:
    """Classify the type of emergency from the pilot message.

    Returns:
        Tuple of (emergency_type, urgency).
    """
    msg = pilot_message.lower()

    if any(kw in msg for kw in MAYDAY_KEYWORDS):
        # Try to identify specific type
        if "engine" in msg:
            return "engine_failure", Urgency.EMERGENCY.value
        if "fire" in msg:
            return "fire", Urgency.EMERGENCY.value
        if "fuel" in msg:
            return "fuel_emergency", Urgency.EMERGENCY.value
        if "medical" in msg:
            return "medical", Urgency.EMERGENCY.value
        return "mayday", Urgency.EMERGENCY.value

    if any(kw in msg for kw in PAN_PAN_KEYWORDS):
        if "medical" in msg:
            return "medical", Urgency.PRIORITY.value
        return "pan_pan", Urgency.PRIORITY.value

    if "squawk 7700" in msg or "7700" in msg:
        return "squawk_7700", Urgency.EMERGENCY.value
    if "squawk 7600" in msg or "7600" in msg:
        return "squawk_7600", Urgency.EMERGENCY.value
    if "squawk 7500" in msg or "7500" in msg:
        return "squawk_7500", Urgency.EMERGENCY.value

    if "engine" in msg and ("failure" in msg or "fire" in msg or "loss" in msg):
        return "engine_failure", Urgency.EMERGENCY.value
    if "fire" in msg or "smoke" in msg:
        return "fire", Urgency.EMERGENCY.value
    if "fuel" in msg and ("emergency" in msg or "bingo" in msg or "minimum" in msg):
        return "fuel_emergency", Urgency.EMERGENCY.value
    if "medical" in msg:
        return "medical", Urgency.PRIORITY.value

    # Generic emergency
    return "generic", Urgency.EMERGENCY.value


def detect_emergency(pilot_message: str) -> bool:
    """Quick check: does the message contain emergency keywords?

    This is used by the live-session graph to decide whether to route
    to the emergency handler.
    """
    msg = pilot_message.lower()
    all_keywords = MAYDAY_KEYWORDS | PAN_PAN_KEYWORDS | EMERGENCY_KEYWORDS
    return any(kw in msg for kw in all_keywords)


def handle_emergency(state: HorusState) -> dict[str, Any]:
    """Generate an emergency ATC response.

    Returns:
        Partial state update with ``atc_response``, ``is_emergency``,
        and appended ``performance_notes``.
    """
    pilot_message = state.get("pilot_message", "")
    context = state.get("context") or {}
    notes = list(state.get("performance_notes") or [])

    callsign = context.get("callsign", "Aircraft calling")
    nearest_airport = context.get("destination", context.get("position", "nearest airport"))
    heading = context.get("heading", "360")
    altitude = context.get("altitude", "3000")

    emergency_type, urgency = _classify_emergency(pilot_message)

    template = EMERGENCY_RESPONSES.get(emergency_type, EMERGENCY_RESPONSES["generic"])
    atc_response = template.format(
        callsign=callsign,
        nearest_airport=nearest_airport,
        heading=heading,
        altitude=altitude,
    )

    notes.append(f"EMERGENCY: {emergency_type} detected (urgency: {urgency})")
    notes.append(f"Student correctly declared emergency — positive training point")

    logger.info(
        "Emergency agent: type=%s, urgency=%s, callsign=%s",
        emergency_type,
        urgency,
        callsign,
    )

    return {
        "atc_response": atc_response,
        "is_emergency": True,
        "performance_notes": notes,
    }
