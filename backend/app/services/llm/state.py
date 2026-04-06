"""Shared state definitions for the Horus multi-agent LangGraph system.

All agents in the orchestrator share a single ``HorusState`` TypedDict that
flows through the graph.  Sub-states (flight plan, weather, fuel, …) are
nested TypedDicts so each agent can read/write only the slice it owns while
the orchestrator keeps everything in one place.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


# ── Enumerations ──────────────────────────────────────────────────────

class SessionPhase(str, Enum):
    """High-level training pipeline phases."""

    INGESTION = "ingestion"
    VALIDATION = "validation"
    PRE_FLIGHT = "pre_flight"
    ACTIVE = "active"
    POST_FLIGHT = "post_flight"
    SCORING = "scoring"
    COMPLETE = "complete"


class FlightCategory(str, Enum):
    """Aviation weather flight categories (FAR 91.155)."""

    VFR = "VFR"
    MVFR = "MVFR"
    IFR = "IFR"
    LIFR = "LIFR"


class Severity(str, Enum):
    """Severity level for validation results and insights."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Urgency(str, Enum):
    """Radio communication urgency level."""

    ROUTINE = "routine"
    PRIORITY = "priority"
    EMERGENCY = "emergency"


# ── Sub-state TypedDicts ──────────────────────────────────────────────

class FlightPlanState(TypedDict, total=False):
    """Flight plan data flowing through validation / execution."""

    departure_icao: str
    arrival_icao: str
    alternate_icao: Optional[str]
    route: list[dict]           # waypoints with lat, lng, name, constraints
    aircraft_type: str
    fuel_on_board: float        # gallons
    fuel_reserve: float         # gallons
    total_weight: float         # lbs
    max_weight: float           # lbs
    flight_rules: str           # "VFR" or "IFR"
    cruise_altitude: int        # feet
    cruise_speed: int           # knots TAS
    estimated_time_enroute: float  # minutes


class WeatherState(TypedDict, total=False):
    """Weather data produced by the weather agent."""

    departure_metar: Optional[str]
    arrival_metar: Optional[str]
    alternate_metar: Optional[str]
    departure_taf: Optional[str]
    arrival_taf: Optional[str]
    flight_category: str        # VFR / MVFR / IFR / LIFR
    hazards: list[str]
    recommendations: list[str]
    briefing_text: str          # LLM-generated natural-language briefing


class FuelState(TypedDict, total=False):
    """Fuel calculation results from the fuel agent."""

    total_burn: float           # gallons
    reserve_required: float     # gallons (legal minimum)
    reserve_available: float    # gallons (fuel_on_board − total_burn)
    legs: list[dict]            # per-leg breakdown
    sufficient: bool
    message: str


class RouteInfo(TypedDict, total=False):
    """Route analysis from the route agent."""

    total_distance_nm: float
    legs: list[dict]            # per-leg distance, heading, ETE
    suggestions: list[str]


class AirspaceInfo(TypedDict, total=False):
    """Airspace analysis from the airspace agent."""

    intersections: list[dict]   # airspace class, restrictions
    required_clearances: list[str]
    required_equipment: list[str]


class AircraftPerformance(TypedDict, total=False):
    """Performance analysis from the performance agent."""

    v_speeds: dict              # Vs, Vx, Vy, Vno, Vne, etc.
    density_altitude: Optional[int]
    climb_rate_fpm: int
    descent_rate_fpm: int
    service_ceiling: int
    altitude_ok: bool
    notes: list[str]


class ValidationResult(TypedDict):
    """Result of a single validation check."""

    agent: str
    passed: bool
    severity: str               # info / warning / critical
    message: str
    details: Optional[dict]


class ScoringResult(TypedDict, total=False):
    """Post-session scoring produced by the student tier + gamification agents."""

    communication_score: float  # 0-100
    decision_score: float       # 0-100
    procedure_score: float      # 0-100
    overall_score: float        # 0-100
    grade: str                  # A / B / C / D / F
    strengths: list[str]
    improvements: list[str]
    summary: str


# ── Master State ──────────────────────────────────────────────────────

class HorusState(TypedDict, total=False):
    """Master state for the Horus orchestrator graph.

    Every node in every sub-graph reads from and writes to a subset of
    these keys.  The ``messages`` list uses LangGraph's ``add_messages``
    reducer so appended messages are automatically merged.
    """

    # ── Core identifiers
    messages: Annotated[list, add_messages]
    session_id: Optional[str]
    user_id: Optional[str]
    phase: str                  # SessionPhase value

    # ── Flight plan & validation
    flight_plan: Optional[FlightPlanState]
    weather: Optional[WeatherState]
    fuel_state: Optional[FuelState]
    route_info: Optional[RouteInfo]
    airspace_info: Optional[AirspaceInfo]
    aircraft_performance: Optional[AircraftPerformance]
    validation_results: list[ValidationResult]
    validation_passed: bool

    # ── Live session
    pilot_message: Optional[str]
    atc_response: Optional[str]
    exchange_count: int
    current_waypoint_index: int
    session_phase_detail: str   # briefing / taxi / takeoff / cruise / approach / landing
    performance_notes: list[str]
    is_emergency: bool

    # ── Scoring & gamification
    scoring: Optional[ScoringResult]
    badges_earned: list[str]

    # ── Context
    language: str               # "en" or "es"
    context: dict               # flight context (callsign, altitude, etc.)
