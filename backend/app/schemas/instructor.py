"""Pydantic schemas for instructor profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InstructorProfileCreate(BaseModel):
    """Schema for creating an instructor profile."""

    qualifications: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    bio: str | None = None
    specializations: list[str] = Field(default_factory=list)
    availability: dict[str, Any] = Field(default_factory=dict)


class InstructorProfileRead(BaseModel):
    """Schema returned when reading an instructor profile."""

    id: uuid.UUID
    user_id: uuid.UUID
    qualifications: list[Any]
    certifications: list[Any]
    bio: str | None = None
    specializations: list[Any]
    availability: dict[str, Any]
    rating: float | None = None
    total_students: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstructorProfileUpdate(BaseModel):
    """Schema for partial instructor profile updates."""

    qualifications: list[str] | None = None
    certifications: list[str] | None = None
    bio: str | None = None
    specializations: list[str] | None = None
    availability: dict[str, Any] | None = None
