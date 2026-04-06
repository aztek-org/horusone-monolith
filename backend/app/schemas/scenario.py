"""Pydantic schemas for Scenario."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScenarioBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    difficulty: int = Field(default=1, ge=1, le=5)
    airport_icao: str = Field(..., min_length=4, max_length=4, pattern="^[A-Z]{4}$")
    runway: str = Field(..., min_length=1, max_length=10)
    weather_preset: str = Field(default="VFR", pattern="^(VFR|MVFR|IFR|LIFR)$")
    phase: str = Field(default="ground")
    scenario_type: str | None = Field(
        default=None,
        pattern=r"^(training|evaluation|emergency|checkride)$",
    )
    flight_plan_template: dict[str, Any] | None = Field(default_factory=dict)


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioResponse(ScenarioBase):
    id: int
    org_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
