"""Pydantic schemas for waypoints, tracks, and flight insights."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Waypoint ──────────────────────────────────────────────────────


class WaypointCreate(BaseModel):
    """Schema for creating a navigation waypoint."""

    name: str = Field(..., min_length=1, max_length=255)
    identifier: str | None = Field(default=None, max_length=10)
    type: str = Field(
        ...,
        pattern=r"^(waypoint|airport|VOR|NDB|fix|intersection)$",
    )
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    frequency: float | None = None
    elevation_ft: int | None = None
    description: str | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict)


class WaypointRead(BaseModel):
    """Schema returned when reading a waypoint."""

    id: uuid.UUID
    name: str
    identifier: str | None = None
    type: str
    lat: float
    lng: float
    frequency: float | None = None
    elevation_ft: int | None = None
    description: str | None = None
    extra_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ScenarioWaypoint ─────────────────────────────────────────────


class ScenarioWaypointCreate(BaseModel):
    """Schema for linking a waypoint to a scenario."""

    waypoint_id: uuid.UUID
    sequence_order: int = Field(..., ge=0)
    altitude_constraint: str | None = Field(default=None, max_length=20)
    speed_constraint: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=500)


class ScenarioWaypointRead(BaseModel):
    """Schema returned when reading a scenario-waypoint association."""

    id: uuid.UUID
    scenario_id: int
    waypoint_id: uuid.UUID
    sequence_order: int
    altitude_constraint: str | None = None
    speed_constraint: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


# ── SessionTrack ──────────────────────────────────────────────────


class SessionTrackRead(BaseModel):
    """Schema returned when reading a session flight track."""

    id: uuid.UUID
    session_id: int
    track_points: list[dict[str, Any]]
    total_distance_nm: float | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


# ── FlightInsight ─────────────────────────────────────────────────


class FlightInsightRead(BaseModel):
    """Schema returned when reading an AI-generated flight insight."""

    id: uuid.UUID
    session_id: int
    type: str
    severity: str
    title: str
    description: str
    timestamp_in_session: float
    extra_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
