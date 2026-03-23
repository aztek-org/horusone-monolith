"""Performance agent — aircraft V-speeds, density altitude, service ceiling.

Checks that the planned altitude is within the aircraft's service ceiling,
estimates density altitude effects on climb performance, and provides
V-speed reference data.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.services.llm.state import HorusState, Severity

logger = logging.getLogger(__name__)

# ── Aircraft performance database (simplified, training-grade) ────────

AIRCRAFT_PERFORMANCE: dict[str, dict[str, Any]] = {
    "C172": {
        "v_speeds": {
            "Vs0": 40,    # Stall speed, landing configuration (KIAS)
            "Vs1": 48,    # Stall speed, clean configuration
            "Vr": 55,     # Rotation speed
            "Vx": 62,     # Best angle of climb
            "Vy": 74,     # Best rate of climb
            "Va": 99,     # Maneuvering speed
            "Vno": 129,   # Max structural cruising
            "Vne": 163,   # Never exceed
            "Vfe": 85,    # Max flap extended
        },
        "climb_rate_fpm": 730,
        "descent_rate_fpm": 500,
        "service_ceiling": 14000,
        "max_gross_weight": 2550,
    },
    "C182": {
        "v_speeds": {
            "Vs0": 49,
            "Vs1": 56,
            "Vr": 60,
            "Vx": 67,
            "Vy": 80,
            "Va": 110,
            "Vno": 140,
            "Vne": 176,
            "Vfe": 95,
        },
        "climb_rate_fpm": 924,
        "descent_rate_fpm": 600,
        "service_ceiling": 18100,
        "max_gross_weight": 3100,
    },
    "PA28": {
        "v_speeds": {
            "Vs0": 44,
            "Vs1": 50,
            "Vr": 60,
            "Vx": 64,
            "Vy": 76,
            "Va": 89,
            "Vno": 125,
            "Vne": 154,
            "Vfe": 103,
        },
        "climb_rate_fpm": 660,
        "descent_rate_fpm": 500,
        "service_ceiling": 14300,
        "max_gross_weight": 2440,
    },
    "B738": {
        "v_speeds": {
            "V1": 140,
            "Vr": 150,
            "V2": 155,
            "Vref": 137,
            "Vmo": 340,
        },
        "climb_rate_fpm": 3000,
        "descent_rate_fpm": 2000,
        "service_ceiling": 41000,
        "max_gross_weight": 174200,
    },
    "A320": {
        "v_speeds": {
            "V1": 135,
            "Vr": 145,
            "V2": 150,
            "Vref": 132,
            "Vmo": 350,
        },
        "climb_rate_fpm": 2800,
        "descent_rate_fpm": 2000,
        "service_ceiling": 39100,
        "max_gross_weight": 170000,
    },
    "DEFAULT": {
        "v_speeds": {
            "Vs0": 45,
            "Vs1": 52,
            "Vr": 58,
            "Vx": 65,
            "Vy": 76,
            "Va": 95,
            "Vno": 130,
            "Vne": 160,
        },
        "climb_rate_fpm": 700,
        "descent_rate_fpm": 500,
        "service_ceiling": 14000,
        "max_gross_weight": 2600,
    },
}


def _estimate_density_altitude(
    field_elevation: int, temperature_c: float, altimeter_inhg: float = 29.92
) -> int:
    """Estimate density altitude using the Koch chart approximation.

    Args:
        field_elevation: Field elevation in feet MSL.
        temperature_c: Outside air temperature (°C).
        altimeter_inhg: Altimeter setting in inches of mercury.

    Returns:
        Density altitude in feet.
    """
    # Pressure altitude
    pressure_alt = field_elevation + (29.92 - altimeter_inhg) * 1000
    # ISA temperature at pressure altitude
    isa_temp = 15.0 - (2.0 * pressure_alt / 1000)
    # Density altitude ≈ pressure altitude + 120 × (OAT − ISA)
    density_alt = pressure_alt + 120 * (temperature_c - isa_temp)
    return int(round(density_alt))


def analyze_performance(state: HorusState) -> dict[str, Any]:
    """Check aircraft performance against planned flight parameters.

    Returns:
        Partial state update with ``aircraft_performance`` and appended
        ``validation_results``.
    """
    results: list[dict[str, Any]] = list(state.get("validation_results") or [])
    flight_plan = state.get("flight_plan") or {}
    weather = state.get("weather") or {}

    aircraft_type = flight_plan.get("aircraft_type", "DEFAULT")
    cruise_altitude = flight_plan.get("cruise_altitude", 5000)

    perf = AIRCRAFT_PERFORMANCE.get(aircraft_type, AIRCRAFT_PERFORMANCE["DEFAULT"])
    v_speeds = perf["v_speeds"]
    service_ceiling = perf["service_ceiling"]
    climb_rate = perf["climb_rate_fpm"]
    descent_rate = perf["descent_rate_fpm"]

    notes: list[str] = []

    # Service ceiling check
    altitude_ok = cruise_altitude <= service_ceiling
    if not altitude_ok:
        notes.append(
            f"Planned altitude {cruise_altitude} ft exceeds service ceiling "
            f"{service_ceiling} ft for {aircraft_type}."
        )

    # Density altitude (use departure weather if available)
    density_alt = None
    from app.services.llm.tools.weather_tools import parse_metar
    dep_metar = weather.get("departure_metar", "")
    if dep_metar:
        parsed = parse_metar(dep_metar)
        temp = parsed.get("temperature")
        altimeter = parsed.get("altimeter", 29.92)
        if temp is not None:
            density_alt = _estimate_density_altitude(0, temp, altimeter)
            if density_alt > service_ceiling:
                notes.append(
                    f"Density altitude ({density_alt} ft) exceeds service ceiling."
                )
            elif density_alt > cruise_altitude:
                notes.append(
                    f"Density altitude ({density_alt} ft) is above planned cruise "
                    f"({cruise_altitude} ft) — climb performance may be degraded."
                )

    # High altitude notes
    if cruise_altitude > 10000:
        notes.append("Cruise above 10,000 ft — 250 KIAS speed limit below FL100 applies during climb/descent.")
    if cruise_altitude > 12500:
        notes.append("Cruise above 12,500 ft — supplemental oxygen required above 12,500 ft MSL after 30 min (FAR 91.211).")

    perf_result: dict[str, Any] = {
        "v_speeds": v_speeds,
        "density_altitude": density_alt,
        "climb_rate_fpm": climb_rate,
        "descent_rate_fpm": descent_rate,
        "service_ceiling": service_ceiling,
        "altitude_ok": altitude_ok,
        "notes": notes,
    }

    # Validation
    if not altitude_ok:
        results.append({
            "agent": "performance",
            "passed": False,
            "severity": Severity.CRITICAL.value,
            "message": (
                f"Planned altitude {cruise_altitude} ft exceeds "
                f"{aircraft_type} service ceiling of {service_ceiling} ft."
            ),
            "details": perf_result,
        })
    else:
        sev = Severity.WARNING.value if notes else Severity.INFO.value
        results.append({
            "agent": "performance",
            "passed": True,
            "severity": sev,
            "message": (
                f"Performance check passed for {aircraft_type} at "
                f"{cruise_altitude} ft."
                + (f" Notes: {'; '.join(notes)}" if notes else "")
            ),
            "details": perf_result,
        })

    logger.info(
        "Performance agent: %s at %d ft — %s",
        aircraft_type,
        cruise_altitude,
        "OK" if altitude_ok else "CEILING EXCEEDED",
    )

    return {
        "aircraft_performance": perf_result,
        "validation_results": results,
    }
