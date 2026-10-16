"""Pydantic schemas for student statistics."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── StudentStats ───────────────────────────────────────────────────


class StudentStatsRead(BaseModel):
    """Schema returned when reading aggregated student statistics."""

    id: uuid.UUID
    user_id: uuid.UUID
    total_flight_hours: float
    total_maneuvers: int
    total_scenarios_completed: int
    total_assessments: int
    overall_score: float
    current_streak: int
    best_streak: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── FlightHourLog ─────────────────────────────────────────────────


class FlightHourLogCreate(BaseModel):
    """Schema for logging a flight hour entry."""

    session_id: int | None = None
    hours_logged: float = Field(..., gt=0)
    maneuvers_practiced: list[str] = Field(default_factory=list)
    phase: str = Field(
        ...,
        pattern=r"^(ground|departure|enroute|approach|landing)$",
    )
    notes: str | None = None


class FlightHourLogRead(BaseModel):
    """Schema returned when reading a flight hour log entry."""

    id: uuid.UUID
    user_id: uuid.UUID
    session_id: int | None = None
    hours_logged: float
    maneuvers_practiced: list[Any]
    phase: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ManeuverLog ───────────────────────────────────────────────────


class ManeuverLogCreate(BaseModel):
    """Schema for logging a maneuver practice record."""

    session_id: int | None = None
    maneuver_name: str = Field(..., min_length=1, max_length=255)
    maneuver_type: str = Field(..., min_length=1, max_length=100)
    score: float | None = Field(default=None, ge=0, le=100)
    duration_seconds: int | None = Field(default=None, ge=0)
    extra_data: dict[str, Any] = Field(default_factory=dict)


class ManeuverLogRead(BaseModel):
    """Schema returned when reading a maneuver log entry."""

    id: uuid.UUID
    user_id: uuid.UUID
    session_id: int | None = None
    maneuver_name: str
    maneuver_type: str
    score: float | None = None
    duration_seconds: int | None = None
    extra_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
