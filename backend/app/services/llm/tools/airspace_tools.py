"""Airspace data tools — mock airspace class lookup and route checks.

In production this would query an FAA NASR / EuroControl database or
a vector-tile service.  For the MVP we provide realistic mock data
for the major US Class-B airports used in training scenarios.
"""

from __future__ import annotations

from typing import Any

# ── Mock airspace database ────────────────────────────────────────────
# Simplified concentric rings for Class B airports.
# Each entry: center (lat, lng), rings [(radius_nm, floor_ft, ceiling_ft)]

AIRSPACE_DB: dict[str, dict[str, Any]] = {
    "KJFK": {
        "class": "B",
        "center": (40.6413, -73.7781),
        "field_elevation": 13,
        "rings": [
            {"radius_nm": 7, "floor_ft": 0, "ceiling_ft": 7000},
            {"radius_nm": 12, "floor_ft": 1500, "ceiling_ft": 7000},
            {"radius_nm": 20, "floor_ft": 3000, "ceiling_ft": 7000},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
            "Student pilot operations require endorsement",
        ],
        "frequencies": {"approach": "132.40", "tower": "119.10", "ground": "121.90"},
    },
    "KLAX": {
        "class": "B",
        "center": (33.9425, -118.4081),
        "field_elevation": 128,
        "rings": [
            {"radius_nm": 5, "floor_ft": 0, "ceiling_ft": 12500},
            {"radius_nm": 15, "floor_ft": 2500, "ceiling_ft": 12500},
            {"radius_nm": 25, "floor_ft": 5000, "ceiling_ft": 12500},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
        ],
        "frequencies": {"approach": "124.50", "tower": "133.90", "ground": "121.65"},
    },
    "KORD": {
        "class": "B",
        "center": (41.9742, -87.9073),
        "field_elevation": 672,
        "rings": [
            {"radius_nm": 5, "floor_ft": 0, "ceiling_ft": 10000},
            {"radius_nm": 10, "floor_ft": 1900, "ceiling_ft": 10000},
            {"radius_nm": 20, "floor_ft": 3000, "ceiling_ft": 10000},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
        ],
        "frequencies": {"approach": "126.90", "tower": "132.70", "ground": "121.75"},
    },
    "KATL": {
        "class": "B",
        "center": (33.6407, -84.4277),
        "field_elevation": 1026,
        "rings": [
            {"radius_nm": 5, "floor_ft": 0, "ceiling_ft": 12500},
            {"radius_nm": 15, "floor_ft": 3000, "ceiling_ft": 12500},
            {"radius_nm": 25, "floor_ft": 5000, "ceiling_ft": 12500},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
        ],
        "frequencies": {"approach": "125.32", "tower": "119.10", "ground": "121.90"},
    },
    "KSFO": {
        "class": "B",
        "center": (37.6213, -122.3790),
        "field_elevation": 13,
        "rings": [
            {"radius_nm": 5, "floor_ft": 0, "ceiling_ft": 8000},
            {"radius_nm": 10, "floor_ft": 1500, "ceiling_ft": 8000},
            {"radius_nm": 20, "floor_ft": 3000, "ceiling_ft": 8000},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
        ],
        "frequencies": {"approach": "135.65", "tower": "120.50", "ground": "121.80"},
    },
    "KDEN": {
        "class": "B",
        "center": (39.8561, -104.6737),
        "field_elevation": 5434,
        "rings": [
            {"radius_nm": 7, "floor_ft": 0, "ceiling_ft": 12000},
            {"radius_nm": 12, "floor_ft": 8000, "ceiling_ft": 12000},
            {"radius_nm": 20, "floor_ft": 10000, "ceiling_ft": 12000},
        ],
        "requirements": [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
        ],
        "frequencies": {"approach": "128.25", "tower": "132.35", "ground": "121.85"},
    },
}

# Generic Class D for any non-Class-B airport we know about
CLASS_D_DEFAULT: dict[str, Any] = {
    "class": "D",
    "rings": [{"radius_nm": 4, "floor_ft": 0, "ceiling_ft": 2500}],
    "requirements": [
        "Two-way radio",
        "Contact tower before entry",
    ],
    "frequencies": {},
}

CLASS_E_DEFAULT: dict[str, Any] = {
    "class": "E",
    "rings": [{"radius_nm": 999, "floor_ft": 700, "ceiling_ft": 17999}],
    "requirements": [],
    "frequencies": {},
}


# ── Lookup functions ──────────────────────────────────────────────────

def _distance_nm(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Quick Haversine (duplicated to keep this module self-contained)."""
    import math

    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 3440.065 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def check_airspace(lat: float, lng: float, altitude: int) -> dict[str, Any]:
    """Check what airspace class a point lies within.

    Args:
        lat, lng: Position in decimal degrees.
        altitude: Altitude MSL in feet.

    Returns:
        Dict with ``class``, ``airport``, ``restrictions``, ``requirements``.
    """
    for icao, data in AIRSPACE_DB.items():
        center_lat, center_lng = data["center"]
        dist = _distance_nm(lat, lng, center_lat, center_lng)

        for ring in data["rings"]:
            if (
                dist <= ring["radius_nm"]
                and ring["floor_ft"] <= altitude <= ring["ceiling_ft"]
            ):
                return {
                    "class": data["class"],
                    "airport": icao,
                    "distance_from_center_nm": round(dist, 1),
                    "floor_ft": ring["floor_ft"],
                    "ceiling_ft": ring["ceiling_ft"],
                    "requirements": data["requirements"],
                    "frequencies": data.get("frequencies", {}),
                }

    # Outside any known Class B — return generic Class E
    return {
        "class": "E",
        "airport": None,
        "distance_from_center_nm": None,
        "floor_ft": 700,
        "ceiling_ft": 17999,
        "requirements": [],
        "frequencies": {},
    }


def get_route_airspace(waypoints: list[dict]) -> list[dict[str, Any]]:
    """Check airspace along a route of waypoints.

    Args:
        waypoints: List of dicts each containing ``lat``, ``lng``,
                   and optionally ``altitude`` (feet MSL).

    Returns:
        List of airspace intersection dicts for each waypoint.
    """
    results: list[dict[str, Any]] = []
    for wp in waypoints:
        lat = wp.get("lat", 0.0)
        lng = wp.get("lng", 0.0)
        alt = wp.get("altitude", 5000)
        info = check_airspace(lat, lng, alt)
        info["waypoint_name"] = wp.get("name", "UNKNOWN")
        results.append(info)
    return results
