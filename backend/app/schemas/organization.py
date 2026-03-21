"""Pydantic schemas for Organization."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    max_seats: int = Field(default=50, ge=1, le=10000)


class OrganizationRead(BaseModel):
    """Schema returned when reading an organization."""

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    is_active: bool
    max_seats: int
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    """Schema for partial organization updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    max_seats: int | None = Field(default=None, ge=1, le=10000)
