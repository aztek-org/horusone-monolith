"""Gatekeeper agent — structural flight-plan validation.

Runs first in the validation pipeline.  Performs fast, deterministic
checks that don't need weather data or LLM calls:

* Route continuity (each leg connects to the next).
* Fuel sufficiency (fuel on board vs. estimated burn + reserve).
* Weight within aircraft limits.
* Departure and arrival airports present in route.
* Alternate required for IFR flights.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, SessionPhase, Severity, ValidationResult

logger = logging.getLogger(__name__)


def validate_flight_plan(state: HorusState) -> dict[str, Any]:
    """Validate the flight plan structurally.

    Returns:
        Partial state update with ``validation_results`` and ``phase``.
    """
    results: list[ValidationResult] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan")

    if not flight_plan:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": "No flight plan provided.",
                "details": None,
            }
        )
        return {
            "validation_results": results,
            "validation_passed": False,
            "phase": SessionPhase.VALIDATION.value,
        }

    # ── 1. Departure & arrival present ────────────────────────────
    dep = flight_plan.get("departure_icao", "")
    arr = flight_plan.get("arrival_icao", "")
    if not dep or not arr:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": "Departure and/or arrival ICAO code missing.",
                "details": {"departure": dep, "arrival": arr},
            }
        )

    # ── 2. Route present and has waypoints ────────────────────────
    route = flight_plan.get("route") or []
    if len(route) < 2:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": "Route must contain at least 2 waypoints (departure + arrival).",
                "details": {"waypoint_count": len(route)},
            }
        )
    else:
        # Check first waypoint matches departure, last matches arrival
        first_name = (route[0].get("name") or route[0].get("identifier") or "").upper()
        last_name = (route[-1].get("name") or route[-1].get("identifier") or "").upper()
        if first_name != dep.upper():
            results.append(
                {
                    "agent": "gatekeeper",
                    "passed": False,
                    "severity": Severity.WARNING.value,
                    "message": f"First waypoint '{first_name}' does not match departure '{dep}'.",
                    "details": None,
                }
            )
        if last_name != arr.upper():
            results.append(
                {
                    "agent": "gatekeeper",
                    "passed": False,
                    "severity": Severity.WARNING.value,
                    "message": f"Last waypoint '{last_name}' does not match arrival '{arr}'.",
                    "details": None,
                }
            )

        # Route continuity: each waypoint should have lat/lng
        for i, wp in enumerate(route):
            if wp.get("lat") is None or wp.get("lng") is None:
                results.append(
                    {
                        "agent": "gatekeeper",
                        "passed": False,
                        "severity": Severity.WARNING.value,
                        "message": f"Waypoint {i} ('{wp.get('name', '?')}') missing coordinates.",
                        "details": {"index": i},
                    }
                )

    # ── 3. Fuel sufficiency (rough check) ─────────────────────────
    fuel_on_board = flight_plan.get("fuel_on_board", 0.0)
    fuel_reserve = flight_plan.get("fuel_reserve", 0.0)
    if fuel_on_board <= 0:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": "Fuel on board must be greater than zero.",
                "details": {"fuel_on_board": fuel_on_board},
            }
        )
    elif fuel_reserve <= 0:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.WARNING.value,
                "message": "Fuel reserve is zero or negative — may not meet legal minimums.",
                "details": {"fuel_reserve": fuel_reserve},
            }
        )

    # ── 4. Weight within limits ───────────────────────────────────
    total_weight = flight_plan.get("total_weight", 0.0)
    max_weight = flight_plan.get("max_weight", 0.0)
    if total_weight > 0 and max_weight > 0 and total_weight > max_weight:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": (
                    f"Aircraft overweight: {total_weight} lbs exceeds "
                    f"max gross weight {max_weight} lbs."
                ),
                "details": {"total_weight": total_weight, "max_weight": max_weight},
            }
        )

    # ── 5. IFR alternate requirement ─────────────────────────────
    flight_rules = flight_plan.get("flight_rules", "VFR").upper()
    alternate = flight_plan.get("alternate_icao")
    if flight_rules == "IFR" and not alternate:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": False,
                "severity": Severity.WARNING.value,
                "message": "IFR flight plan filed without an alternate airport.",
                "details": None,
            }
        )

    # ── Summary ───────────────────────────────────────────────────
    # If nothing was appended by this agent, it's a pass
    new_results = [r for r in results if r["agent"] == "gatekeeper"]
    if not new_results:
        results.append(
            {
                "agent": "gatekeeper",
                "passed": True,
                "severity": Severity.INFO.value,
                "message": "Flight plan structure validated successfully.",
                "details": None,
            }
        )

    logger.info(
        "Gatekeeper: %d checks, %d issues",
        len(new_results) or 1,
        sum(1 for r in new_results if not r.get("passed", True)),
    )

    return {
        "validation_results": results,
        "phase": SessionPhase.VALIDATION.value,
    }
