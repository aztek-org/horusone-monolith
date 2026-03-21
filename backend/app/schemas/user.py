"""Pydantic schemas for User."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=255)
    keycloak_id: str = Field(..., min_length=1, max_length=255)


class UserRead(BaseModel):
    """Schema returned when reading a user."""

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for partial user updates."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=2048)
