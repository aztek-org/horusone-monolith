"""Pure-math aviation calculation tools.

All functions are synchronous and stateless — no I/O, no LLM calls.  They
can be used directly by agents or wrapped as LangChain ``@tool`` callables.
"""

from __future__ import annotations

import math
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────

EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles

# Default fuel-burn rates (gallons per hour) by aircraft type.
# These are *training-grade* approximations, not ops manuals.
FUEL_BURN_RATES: dict[str, float] = {
    "C172": 8.5,  # Cessna 172
    "C182": 12.0,  # Cessna 182
    "PA28": 9.0,  # Piper Cherokee
    "PA44": 16.0,  # Piper Seminole (twin)
    "BE36": 14.0,  # Beechcraft Bonanza
    "B738": 850.0,  # Boeing 737-800
    "A320": 800.0,  # Airbus A320
    "DEFAULT": 10.0,
}

# Typical cruise TAS (knots) when not specified.
DEFAULT_TAS: dict[str, int] = {
    "C172": 110,
    "C182": 140,
    "PA28": 120,
    "PA44": 160,
    "BE36": 170,
    "B738": 460,
    "A320": 450,
    "DEFAULT": 120,
}

# Empty-weight + typical arm data for W&B (simplified).
AIRCRAFT_DATA: dict[str, dict[str, Any]] = {
    "C172": {
        "empty_weight": 1680,
        "max_gross": 2550,
        "cg_range": (35.0, 47.3),  # inches aft of datum
        "fuel_arm": 48.0,
        "payload_arm": 40.0,
    },
    "PA28": {
        "empty_weight": 1410,
        "max_gross": 2440,
        "cg_range": (82.0, 93.0),
        "fuel_arm": 95.0,
        "payload_arm": 85.0,
    },
    "DEFAULT": {
        "empty_weight": 1700,
        "max_gross": 2600,
        "cg_range": (35.0, 47.0),
        "fuel_arm": 48.0,
        "payload_arm": 40.0,
    },
}


# ── Distance & Navigation ────────────────────────────────────────────


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance between two points.

    Args:
        lat1, lon1: Origin coordinates (decimal degrees).
        lat2, lon2: Destination coordinates (decimal degrees).

    Returns:
        Distance in nautical miles.
    """
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_NM * c


def calculate_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial true bearing from point 1 to point 2.

    Returns:
        Heading in degrees (0-360).
    """
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    x = math.sin(d_lambda) * math.cos(φ2)
    y = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(d_lambda)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_groundspeed(
    true_airspeed: float,
    wind_direction: float,
    wind_speed: float,
    heading: float,
) -> float:
    """Calculate groundspeed given TAS, wind, and heading.

    Uses the wind-triangle approximation.

    Args:
        true_airspeed: TAS in knots.
        wind_direction: Direction wind is coming *from* (degrees true).
        wind_speed: Wind speed in knots.
        heading: Aircraft true heading in degrees.

    Returns:
        Groundspeed in knots.
    """
    # Head/tail-wind component
    wind_angle = math.radians(wind_direction - heading)
    headwind = wind_speed * math.cos(wind_angle)
    # Groundspeed = TAS − headwind (headwind positive = reduces GS)
    gs = true_airspeed - headwind
    return max(gs, 0.0)


def calculate_ete(distance_nm: float, groundspeed_kts: float) -> float:
    """Estimated time en-route.

    Args:
        distance_nm: Distance in nautical miles.
        groundspeed_kts: Groundspeed in knots.

    Returns:
        Time in minutes.
    """
    if groundspeed_kts <= 0:
        return 0.0
    return (distance_nm / groundspeed_kts) * 60.0


# ── Fuel ──────────────────────────────────────────────────────────────


def calculate_fuel_burn(
    distance_nm: float,
    aircraft_type: str,
    altitude: int = 5000,
    wind_component: float = 0.0,
    tas_override: float | None = None,
) -> float:
    """Estimate fuel burn for a leg.

    Args:
        distance_nm: Leg distance in NM.
        aircraft_type: ICAO aircraft designator (e.g. "C172").
        altitude: Planned altitude (feet MSL).  Higher = leaner burn.
        wind_component: Headwind (+) or tailwind (−) in knots.
        tas_override: Override TAS if known.

    Returns:
        Fuel burn in gallons.
    """
    gph = FUEL_BURN_RATES.get(aircraft_type, FUEL_BURN_RATES["DEFAULT"])
    tas = tas_override or DEFAULT_TAS.get(aircraft_type, DEFAULT_TAS["DEFAULT"])

    # Rough altitude correction: −2 % GPH per 5 000 ft above sea level
    alt_factor = max(1.0 - 0.02 * (altitude / 5000), 0.8)
    gph *= alt_factor

    gs = max(tas - wind_component, 30.0)
    time_hours = distance_nm / gs
    return round(gph * time_hours, 2)


def calculate_fuel_reserve(flight_rules: str, fuel_burn_rate_gph: float) -> float:
    """Minimum legal fuel reserve.

    FAR 91.151 (VFR): 30 min day / 45 min night → we use 45 min.
    FAR 91.167 (IFR): 45 min at normal cruise.

    Returns:
        Reserve in gallons.
    """
    minutes = 45.0 if flight_rules.upper() == "IFR" else 45.0  # conservative
    return round(fuel_burn_rate_gph * (minutes / 60.0), 2)


# ── Weight & Balance ──────────────────────────────────────────────────


def calculate_weight_balance(
    aircraft_type: str,
    fuel_weight: float,
    payload: float,
    fuel_arm: float | None = None,
    payload_arm: float | None = None,
) -> dict[str, Any]:
    """Simplified weight-and-balance check.

    Args:
        aircraft_type: ICAO designator.
        fuel_weight: Fuel weight in lbs (≈ gallons × 6.0 for avgas).
        payload: Payload weight in lbs (pilot + pax + bags).
        fuel_arm: Arm of fuel (inches aft of datum).  Auto-looked-up if None.
        payload_arm: Arm of payload.  Auto-looked-up if None.

    Returns:
        Dict with total_weight, cg_position, within_limits.
    """
    data = AIRCRAFT_DATA.get(aircraft_type, AIRCRAFT_DATA["DEFAULT"])
    empty_w = data["empty_weight"]
    max_gross = data["max_gross"]
    f_arm = fuel_arm or data["fuel_arm"]
    p_arm = payload_arm or data["payload_arm"]
    cg_fwd, cg_aft = data["cg_range"]

    total_weight = empty_w + fuel_weight + payload
    # Moment = Σ(weight × arm) — simplified: assume empty-weight CG at mid-range
    empty_cg = (cg_fwd + cg_aft) / 2.0
    total_moment = (empty_w * empty_cg) + (fuel_weight * f_arm) + (payload * p_arm)
    cg_position = total_moment / total_weight if total_weight > 0 else 0.0

    within_weight = total_weight <= max_gross
    within_cg = cg_fwd <= cg_position <= cg_aft

    return {
        "total_weight": round(total_weight, 1),
        "max_gross": max_gross,
        "cg_position": round(cg_position, 2),
        "cg_range": {"forward": cg_fwd, "aft": cg_aft},
        "within_weight": within_weight,
        "within_cg": within_cg,
        "within_limits": within_weight and within_cg,
    }
