"""Pydantic schemas for Seat."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SeatCreate(BaseModel):
    """Schema for creating a new seat (assigning a user to an org)."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str = Field(
        default="student",
        pattern=r"^(admin|instructor|student)$",
    )


class SeatRead(BaseModel):
    """Schema returned when reading a seat."""

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class SeatUpdate(BaseModel):
    """Schema for partial seat updates."""

    role: str | None = Field(
        default=None,
        pattern=r"^(admin|instructor|student)$",
    )
    is_active: bool | None = None
