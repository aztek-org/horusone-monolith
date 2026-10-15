"""Route agent — distance, heading, ETE computation and suggestions.

Iterates through the flight plan route and produces per-leg navigation
data.  Optionally suggests improvements (e.g. direct-to short-cuts).
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, Severity
from app.services.llm.tools.calculation_tools import (
    DEFAULT_TAS,
    calculate_distance,
    calculate_ete,
    calculate_groundspeed,
    calculate_heading,
)

logger = logging.getLogger(__name__)


def optimize_route(state: HorusState) -> dict[str, Any]:
    """Compute per-leg navigation details and total route statistics.

    Returns:
        Partial state update with ``route_info`` and appended
        ``validation_results``.
    """
    results: list[dict[str, Any]] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan") or {}

    route = flight_plan.get("route") or []
    aircraft_type = flight_plan.get("aircraft_type", "DEFAULT")
    cruise_speed = flight_plan.get("cruise_speed", 0)
    if not cruise_speed:
        cruise_speed = DEFAULT_TAS.get(aircraft_type, DEFAULT_TAS["DEFAULT"])

    legs: list[dict[str, Any]] = []
    total_distance = 0.0
    total_ete = 0.0
    suggestions: list[str] = []

    for i in range(len(route) - 1):
        wp_from = route[i]
        wp_to = route[i + 1]

        lat1 = wp_from.get("lat", 0.0)
        lon1 = wp_from.get("lng", 0.0)
        lat2 = wp_to.get("lat", 0.0)
        lon2 = wp_to.get("lng", 0.0)

        distance = calculate_distance(lat1, lon1, lat2, lon2)
        heading = calculate_heading(lat1, lon1, lat2, lon2)

        # Wind
        wind_data = wp_to.get("wind") or {}
        wind_dir = wind_data.get("direction", 0)
        wind_spd = wind_data.get("speed", 0)
        gs = calculate_groundspeed(cruise_speed, wind_dir, wind_spd, heading)
        ete = calculate_ete(distance, gs)

        total_distance += distance
        total_ete += ete

        legs.append(
            {
                "leg": i + 1,
                "from": wp_from.get("name", f"WP{i}"),
                "to": wp_to.get("name", f"WP{i + 1}"),
                "distance_nm": round(distance, 1),
                "heading_deg": round(heading, 0),
                "groundspeed_kts": round(gs, 0),
                "ete_minutes": round(ete, 1),
            }
        )

    # Direct distance for comparison
    if len(route) >= 2:
        first_wp, last_wp = route[0], route[-1]
        direct_dist = calculate_distance(
            first_wp.get("lat", 0.0),
            first_wp.get("lng", 0.0),
            last_wp.get("lat", 0.0),
            last_wp.get("lng", 0.0),
        )
        overhead_pct = (
            ((total_distance - direct_dist) / direct_dist * 100) if direct_dist > 0 else 0
        )
        if overhead_pct > 20:
            suggestions.append(
                f"Route is {overhead_pct:.0f}% longer than direct "
                f"({total_distance:.0f} NM vs {direct_dist:.0f} NM). "
                "Consider requesting direct-to if airspace permits."
            )

    # Very short legs might be unnecessary
    for leg in legs:
        if leg["distance_nm"] < 5.0 and len(legs) > 2:
            suggestions.append(
                f"Leg {leg['leg']} ({leg['from']}→{leg['to']}) is only "
                f"{leg['distance_nm']} NM — consider consolidating."
            )

    route_info = {
        "total_distance_nm": round(total_distance, 1),
        "total_ete_minutes": round(total_ete, 1),
        "legs": legs,
        "suggestions": suggestions,
    }

    results.append(
        {
            "agent": "route",
            "passed": True,
            "severity": Severity.INFO.value,
            "message": (f"Route analysed: {total_distance:.0f} NM, ETE {total_ete:.0f} min."),
            "details": {
                "total_distance_nm": round(total_distance, 1),
                "total_ete_minutes": round(total_ete, 1),
                "leg_count": len(legs),
            },
        }
    )

    if suggestions:
        results.append(
            {
                "agent": "route",
                "passed": True,
                "severity": Severity.WARNING.value,
                "message": f"Route suggestions: {'; '.join(suggestions)}",
                "details": {"suggestions": suggestions},
            }
        )

    logger.info(
        "Route agent: %.0f NM, %.0f min, %d suggestions",
        total_distance,
        total_ete,
        len(suggestions),
    )

    return {
        "route_info": route_info,
        "validation_results": results,
    }
