"""Pydantic schemas for TrainingModule."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.scenario import ScenarioResponse


class TrainingModuleCreate(BaseModel):
    """Schema for creating a new training module."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    org_id: uuid.UUID | None = None
    difficulty_level: int = Field(default=1, ge=1, le=5)
    estimated_duration_minutes: int | None = Field(default=None, ge=1)


class TrainingModuleRead(BaseModel):
    """Schema returned when reading a training module."""

    id: uuid.UUID
    name: str
    description: str | None = None
    org_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    is_published: bool
    difficulty_level: int
    estimated_duration_minutes: int | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TrainingModuleWithScenarios(TrainingModuleRead):
    """Training module with its associated scenarios eagerly loaded."""

    scenarios: list[ScenarioResponse] = []


class TrainingModuleUpdate(BaseModel):
    """Schema for partial training module updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_published: bool | None = None
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    estimated_duration_minutes: int | None = Field(default=None, ge=1)
    sort_order: int | None = Field(default=None, ge=0)


class ModuleScenarioAction(BaseModel):
    """Schema for adding / reordering a scenario within a module."""

    scenario_id: int
    sort_order: int = Field(default=0, ge=0)
