"""Airspace agent — airspace class identification and requirement checks.

Checks each route waypoint against the mock airspace database and
identifies required clearances, equipment, and frequencies.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.state import HorusState, Severity
from app.services.llm.tools.airspace_tools import get_route_airspace

logger = logging.getLogger(__name__)


def check_airspace_restrictions(state: HorusState) -> dict[str, Any]:
    """Analyse airspace along the flight plan route.

    Returns:
        Partial state update with ``airspace_info`` and appended
        ``validation_results``.
    """
    results: list[dict[str, Any]] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan") or {}

    route = flight_plan.get("route") or []
    cruise_altitude = flight_plan.get("cruise_altitude", 5000)

    # Enrich waypoints with altitude for the airspace check
    enriched: list[dict[str, Any]] = []
    for wp in route:
        alt = wp.get("altitude", cruise_altitude)
        if isinstance(alt, str):
            try:
                alt = int(alt)
            except ValueError:
                alt = cruise_altitude
        enriched.append(
            {
                "lat": wp.get("lat", 0.0),
                "lng": wp.get("lng", 0.0),
                "name": wp.get("name", "UNKNOWN"),
                "altitude": alt,
            }
        )

    intersections = get_route_airspace(enriched)

    # Aggregate requirements
    all_requirements: set[str] = set()
    all_equipment: set[str] = set()
    class_b_entries: list[str] = []

    for info in intersections:
        airspace_class = info.get("class", "E")
        wp_name = info.get("waypoint_name", "?")

        for req in info.get("requirements", []):
            all_requirements.add(req)

        if airspace_class == "B":
            class_b_entries.append(wp_name)
            all_equipment.add("Transponder with Mode C")
            all_equipment.add("Two-way radio")
        elif airspace_class == "C":
            all_equipment.add("Transponder with Mode C")
            all_equipment.add("Two-way radio")
        elif airspace_class == "D":
            all_equipment.add("Two-way radio")

    airspace_info = {
        "intersections": intersections,
        "required_clearances": sorted(all_requirements),
        "required_equipment": sorted(all_equipment),
    }

    # Validation results
    if class_b_entries:
        results.append(
            {
                "agent": "airspace",
                "passed": True,
                "severity": Severity.WARNING.value,
                "message": (
                    f"Route enters Class B airspace near: "
                    f"{', '.join(class_b_entries)}. ATC clearance required."
                ),
                "details": {"class_b_waypoints": class_b_entries},
            }
        )
    else:
        results.append(
            {
                "agent": "airspace",
                "passed": True,
                "severity": Severity.INFO.value,
                "message": "Route does not intersect Class B airspace.",
                "details": None,
            }
        )

    if all_equipment:
        results.append(
            {
                "agent": "airspace",
                "passed": True,
                "severity": Severity.INFO.value,
                "message": f"Required equipment: {', '.join(sorted(all_equipment))}.",
                "details": {"equipment": sorted(all_equipment)},
            }
        )

    logger.info(
        "Airspace agent: %d intersections, %d Class B entries",
        len(intersections),
        len(class_b_entries),
    )

    return {
        "airspace_info": airspace_info,
        "validation_results": results,
    }
