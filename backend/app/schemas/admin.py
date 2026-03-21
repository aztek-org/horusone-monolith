"""Pydantic schemas for admin API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.seat import SeatRead


class OrganizationWithStats(BaseModel):
    """Organization with aggregated statistics.

    Extends the basic organization fields with live counts for seats,
    active sessions, and scenarios.
    """

    id: uuid.UUID
    name: str
    slug: str
    logo_url: str | None = None
    is_active: bool
    max_seats: int
    created_at: datetime
    seat_count: int = 0
    active_sessions: int = 0
    scenario_count: int = 0

    model_config = {"from_attributes": True}


class SeatWithUser(BaseModel):
    """Seat enriched with associated user details.

    Includes the user's email and display name alongside the standard
    seat fields so the admin UI can render a member list without extra
    round-trips.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    is_active: bool
    joined_at: datetime
    user_email: str
    user_display_name: str

    model_config = {"from_attributes": True}


class SeatCreateRequest(BaseModel):
    """Request body to add a user to an organization by email.

    The server looks up the user by ``email`` and creates a seat with
    the given ``role``.
    """

    email: EmailStr
    role: str = Field(
        default="student",
        pattern=r"^(admin|instructor|student)$",
    )


class SeatRoleUpdate(BaseModel):
    """Request body to update a seat's role."""

    role: str = Field(
        ...,
        pattern=r"^(admin|instructor|student)$",
    )


class AdminUserUpdate(BaseModel):
    """Admin request to update a user's profile or active status."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserWithSeats(BaseModel):
    """User details with their organization memberships (seats)."""

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    seats: list[SeatRead] = []

    model_config = {"from_attributes": True}


class AdminStats(BaseModel):
    """Platform-wide statistics for the admin dashboard."""

    total_orgs: int
    total_users: int
    total_sessions: int
    total_scenarios: int
