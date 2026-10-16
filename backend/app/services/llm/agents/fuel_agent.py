"""Fuel agent — per-leg fuel burn calculation and legal reserve check.

Uses the calculation tools to compute fuel burn for each route leg,
then validates that fuel on board covers total burn plus legal reserves.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, Severity, ValidationResult
from app.services.llm.tools.calculation_tools import (
    FUEL_BURN_RATES,
    calculate_distance,
    calculate_fuel_burn,
    calculate_fuel_reserve,
)

logger = logging.getLogger(__name__)


def calculate_fuel(state: HorusState) -> dict[str, Any]:
    """Calculate per-leg fuel burn and validate reserves.

    Returns:
        Partial state update with ``fuel_state`` and appended
        ``validation_results``.
    """
    results: list[ValidationResult] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan") or {}

    route = flight_plan.get("route") or []
    aircraft_type = flight_plan.get("aircraft_type", "DEFAULT")
    fuel_on_board = flight_plan.get("fuel_on_board", 0.0)
    flight_rules = flight_plan.get("flight_rules", "VFR").upper()
    cruise_altitude = flight_plan.get("cruise_altitude", 5000)

    # Get wind from weather state if available
    _weather = state.get("weather") or {}

    legs: list[dict[str, Any]] = []
    total_burn = 0.0

    for i in range(len(route) - 1):
        wp_from = route[i]
        wp_to = route[i + 1]

        lat1 = wp_from.get("lat", 0.0)
        lon1 = wp_from.get("lng", 0.0)
        lat2 = wp_to.get("lat", 0.0)
        lon2 = wp_to.get("lng", 0.0)

        # Altitude for this leg (use waypoint constraint or cruise)
        leg_alt = wp_to.get("altitude", cruise_altitude)
        if isinstance(leg_alt, str):
            try:
                leg_alt = int(leg_alt.replace("FL", "").strip()) * (
                    100 if "FL" in str(wp_to.get("altitude", "")) else 1
                )
            except ValueError:
                leg_alt = cruise_altitude

        distance = calculate_distance(lat1, lon1, lat2, lon2)

        # Wind component — extract from leg wind data or assume calm
        wind_data = wp_to.get("wind") or {}
        wind_component = wind_data.get("headwind", 0.0)

        burn = calculate_fuel_burn(
            distance_nm=distance,
            aircraft_type=aircraft_type,
            altitude=leg_alt,
            wind_component=wind_component,
        )
        total_burn += burn

        legs.append(
            {
                "leg": i + 1,
                "from": wp_from.get("name", f"WP{i}"),
                "to": wp_to.get("name", f"WP{i + 1}"),
                "distance_nm": round(distance, 1),
                "altitude_ft": leg_alt,
                "fuel_burn_gal": burn,
            }
        )

    # Legal reserve
    gph = FUEL_BURN_RATES.get(aircraft_type, FUEL_BURN_RATES["DEFAULT"])
    reserve_required = calculate_fuel_reserve(flight_rules, gph)
    reserve_available = fuel_on_board - total_burn
    sufficient = reserve_available >= reserve_required

    fuel_state = {
        "total_burn": round(total_burn, 2),
        "reserve_required": reserve_required,
        "reserve_available": round(reserve_available, 2),
        "legs": legs,
        "sufficient": sufficient,
        "message": (
            f"Total fuel burn: {total_burn:.1f} gal. "
            f"Reserve available: {reserve_available:.1f} gal "
            f"(required: {reserve_required:.1f} gal). "
            + ("SUFFICIENT." if sufficient else "INSUFFICIENT — add fuel or reduce route.")
        ),
    }

    # Validation result
    if not sufficient:
        results.append(
            {
                "agent": "fuel",
                "passed": False,
                "severity": Severity.CRITICAL.value,
                "message": (
                    f"Insufficient fuel: {fuel_on_board:.1f} gal on board, "
                    f"{total_burn:.1f} gal burn + {reserve_required:.1f} gal reserve needed."
                ),
                "details": {
                    "fuel_on_board": fuel_on_board,
                    "total_burn": round(total_burn, 2),
                    "reserve_required": reserve_required,
                    "reserve_available": round(reserve_available, 2),
                },
            }
        )
    else:
        results.append(
            {
                "agent": "fuel",
                "passed": True,
                "severity": Severity.INFO.value,
                "message": (
                    f"Fuel sufficient: {reserve_available:.1f} gal reserve "
                    f"(min {reserve_required:.1f} gal)."
                ),
                "details": {
                    "total_burn": round(total_burn, 2),
                    "reserve_available": round(reserve_available, 2),
                },
            }
        )

    logger.info(
        "Fuel agent: %.1f gal burn, %.1f gal reserve (%s)",
        total_burn,
        reserve_available,
        "OK" if sufficient else "INSUFFICIENT",
    )

    return {
        "fuel_state": fuel_state,
        "validation_results": results,
    }
