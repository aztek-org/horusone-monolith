"""Waypoint, scenario-waypoint, session-track, and flight-insight API routes.

- ``GET  /``                                    — search waypoints
- ``POST /``                                    — create waypoint (instructor+)
- ``GET  /scenarios/{scenario_id}/waypoints``   — scenario route waypoints
- ``POST /scenarios/{scenario_id}/waypoints``   — add waypoint to scenario
- ``GET  /sessions/{session_id}/track``         — session flight track
- ``GET  /sessions/{session_id}/insights``      — session flight insights
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.waypoint_repository import WaypointRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import RequireActiveSeat
from app.schemas.waypoint import (
    FlightInsightRead,
    ScenarioWaypointCreate,
    ScenarioWaypointRead,
    SessionTrackRead,
    WaypointCreate,
    WaypointRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/waypoints", tags=["Waypoints"])

waypoint_repo = WaypointRepository()


# ── Waypoint search / create ───────────────────────────────────────


@router.get("/", response_model=list[WaypointRead])
async def search_waypoints(
    _user: CurrentUser,
    type: str | None = Query(default=None, alias="type"),
    near_lat: float | None = Query(default=None, ge=-90, le=90),
    near_lng: float | None = Query(default=None, ge=-180, le=180),
    radius: float = Query(default=50.0, ge=1, le=500),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> list[WaypointRead]:
    """Search waypoints by type and/or proximity.

    When ``near_lat`` and ``near_lng`` are provided, results are
    filtered to waypoints within ``radius`` nautical miles.
    """
    waypoints = await waypoint_repo.search_waypoints(
        db,
        wp_type=type,
        near_lat=near_lat,
        near_lng=near_lng,
        radius_nm=radius,
        limit=limit,
    )
    return waypoints  # type: ignore[return-value]


@router.post(
    "/",
    response_model=WaypointRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_waypoint(
    data: WaypointCreate,
    _user: RequireInstructor,
    _seat: RequireActiveSeat,
    db: AsyncSession = Depends(get_db_session),
) -> WaypointRead:
    """Create a new navigation waypoint.

    Requires instructor role or higher and an active seat.
    """
    waypoint = await waypoint_repo.create_waypoint(db, data.model_dump())
    return waypoint  # type: ignore[return-value]


# ── Scenario waypoints ─────────────────────────────────────────────


@router.get(
    "/scenarios/{scenario_id}/waypoints",
    response_model=list[ScenarioWaypointRead],
)
async def get_scenario_waypoints(
    scenario_id: int,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> list[ScenarioWaypointRead]:
    """Get the ordered list of waypoints for a scenario."""
    waypoints = await waypoint_repo.get_scenario_waypoints(db, scenario_id)
    return waypoints  # type: ignore[return-value]


@router.post(
    "/scenarios/{scenario_id}/waypoints",
    response_model=ScenarioWaypointRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_scenario_waypoint(
    scenario_id: int,
    data: ScenarioWaypointCreate,
    _user: RequireInstructor,
    _seat: RequireActiveSeat,
    db: AsyncSession = Depends(get_db_session),
) -> ScenarioWaypointRead:
    """Add a waypoint to a scenario at a given sequence position.

    Requires instructor role or higher and an active seat.
    """
    sw = await waypoint_repo.add_scenario_waypoint(
        db,
        scenario_id=scenario_id,
        waypoint_id=data.waypoint_id,
        sequence=data.sequence_order,
        altitude_constraint=data.altitude_constraint,
        speed_constraint=data.speed_constraint,
        notes=data.notes,
    )
    return sw  # type: ignore[return-value]


# ── Session tracks & insights ──────────────────────────────────────


@router.get(
    "/sessions/{session_id}/track",
    response_model=SessionTrackRead | None,
)
async def get_session_track(
    session_id: int,
    _user: CurrentUser,
    _seat: RequireActiveSeat,
    db: AsyncSession = Depends(get_db_session),
) -> SessionTrackRead | None:
    """Get the recorded flight track for a training session."""
    track = await waypoint_repo.get_session_track(db, session_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No track found for session {session_id}",
        )
    return track  # type: ignore[return-value]


@router.get(
    "/sessions/{session_id}/insights",
    response_model=list[FlightInsightRead],
)
async def get_session_insights(
    session_id: int,
    _user: CurrentUser,
    _seat: RequireActiveSeat,
    db: AsyncSession = Depends(get_db_session),
) -> list[FlightInsightRead]:
    """Get AI-generated flight insights for a training session."""
    insights = await waypoint_repo.get_flight_insights(db, session_id)
    return insights  # type: ignore[return-value]
