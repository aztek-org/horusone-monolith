"""Pydantic schemas for flight plans and legs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── FlightPlan ────────────────────────────────────────────────────


class FlightPlanCreate(BaseModel):
    """Schema for creating a flight plan."""

    scenario_id: int | None = None
    org_id: uuid.UUID | None = None
    title: str = Field(..., min_length=1, max_length=255)
    departure_icao: str = Field(..., min_length=3, max_length=4, pattern=r"^[A-Z0-9]{3,4}$")
    arrival_icao: str = Field(..., min_length=3, max_length=4, pattern=r"^[A-Z0-9]{3,4}$")
    alternate_icao: str | None = Field(default=None, max_length=4, pattern=r"^[A-Z0-9]{3,4}$")
    route_string: str | None = None
    aircraft_type: str | None = Field(default=None, max_length=50)
    fuel_required_gal: float | None = Field(default=None, ge=0)
    fuel_reserve_gal: float | None = Field(default=None, ge=0)
    total_weight_lbs: float | None = Field(default=None, ge=0)
    max_weight_lbs: float | None = Field(default=None, ge=0)
    cg_position: float | None = None
    weather_briefing: dict[str, Any] = Field(default_factory=dict)
    airspace_restrictions: list[Any] = Field(default_factory=list)
    notes: str | None = None
    source_type: str = Field(
        default="form",
        pattern=r"^(form|ocr|text|image)$",
    )
    status: str = Field(
        default="draft",
        pattern=(r"^(draft|validated|approved|active|completed)$"),
    )


class FlightPlanRead(BaseModel):
    """Schema returned when reading a flight plan."""

    id: uuid.UUID
    user_id: uuid.UUID
    scenario_id: int | None = None
    org_id: uuid.UUID | None = None
    title: str
    departure_icao: str
    arrival_icao: str
    alternate_icao: str | None = None
    route_string: str | None = None
    aircraft_type: str | None = None
    fuel_required_gal: float | None = None
    fuel_reserve_gal: float | None = None
    total_weight_lbs: float | None = None
    max_weight_lbs: float | None = None
    cg_position: float | None = None
    weather_briefing: dict[str, Any]
    airspace_restrictions: list[Any]
    notes: str | None = None
    source_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    legs: list[FlightPlanLegRead] = []

    model_config = {"from_attributes": True}


class FlightPlanUpdate(BaseModel):
    """Schema for partial flight plan updates."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    alternate_icao: str | None = Field(default=None, max_length=4)
    route_string: str | None = None
    aircraft_type: str | None = Field(default=None, max_length=50)
    fuel_required_gal: float | None = Field(default=None, ge=0)
    fuel_reserve_gal: float | None = Field(default=None, ge=0)
    total_weight_lbs: float | None = Field(default=None, ge=0)
    max_weight_lbs: float | None = Field(default=None, ge=0)
    cg_position: float | None = None
    weather_briefing: dict[str, Any] | None = None
    airspace_restrictions: list[Any] | None = None
    notes: str | None = None
    status: str | None = Field(
        default=None,
        pattern=(r"^(draft|validated|approved|active|completed)$"),
    )


# ── FlightPlanLeg ────────────────────────────────────────────────


class FlightPlanLegCreate(BaseModel):
    """Schema for creating a flight plan leg."""

    sequence: int = Field(..., ge=0)
    from_waypoint_id: uuid.UUID | None = None
    to_waypoint_id: uuid.UUID | None = None
    from_identifier: str | None = Field(default=None, max_length=10)
    to_identifier: str | None = Field(default=None, max_length=10)
    distance_nm: float | None = Field(default=None, ge=0)
    magnetic_heading: float | None = Field(default=None, ge=0, le=360)
    altitude: str | None = Field(default=None, max_length=20)
    estimated_time_minutes: float | None = Field(default=None, ge=0)
    fuel_burn_gal: float | None = Field(default=None, ge=0)
    wind: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=500)


class FlightPlanLegRead(BaseModel):
    """Schema returned when reading a flight plan leg."""

    id: uuid.UUID
    flight_plan_id: uuid.UUID
    sequence: int
    from_waypoint_id: uuid.UUID | None = None
    to_waypoint_id: uuid.UUID | None = None
    from_identifier: str | None = None
    to_identifier: str | None = None
    distance_nm: float | None = None
    magnetic_heading: float | None = None
    altitude: str | None = None
    estimated_time_minutes: float | None = None
    fuel_burn_gal: float | None = None
    wind: dict[str, Any] | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


# ── Special input schemas ─────────────────────────────────────────


class FlightPlanFromText(BaseModel):
    """Schema for creating a flight plan from free-text input."""

    text: str = Field(
        ...,
        min_length=10,
        description="Free-text flight plan description to parse.",
    )
    title: str | None = Field(default=None, max_length=255)
    org_id: uuid.UUID | None = None


class FlightPlanFromImage(BaseModel):
    """Schema for creating a flight plan from an image upload.

    The ``image_base64`` field contains the Base64-encoded image data
    to be processed via OCR.
    """

    image_base64: str = Field(
        ...,
        min_length=100,
        description="Base64-encoded image of a flight plan form.",
    )
    title: str | None = Field(default=None, max_length=255)
    org_id: uuid.UUID | None = None


# ── Validation response ────────────────────────────────────────────


class ValidationResult(BaseModel):
    """A single validation check result from an agent."""

    agent: str
    passed: bool = False
    severity: str = "info"
    message: str


class ValidationResponse(BaseModel):
    """Response from the flight plan validation pipeline."""

    plan_id: str
    valid: bool
    results: list[ValidationResult] = []
    weather: dict[str, Any] | None = None
    fuel_state: dict[str, Any] | None = None
    route_info: dict[str, Any] | None = None
    airspace_info: dict[str, Any] | None = None
    aircraft_performance: dict[str, Any] | None = None
    session_id: str | None = None
