"""Pydantic schemas for gamification — badges, awards, leaderboards."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Badge ─────────────────────────────────────────────────────────


class BadgeRead(BaseModel):
    """Schema returned when reading a badge definition."""

    id: uuid.UUID
    org_id: uuid.UUID | None = None
    name: str
    slug: str
    description: str
    icon: str | None = None
    criteria: dict[str, Any]
    category: str
    tier: str
    sort_order: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BadgeCriteria(BaseModel):
    """Validated badge criteria payload for badge creation."""

    type: str = Field(
        ...,
        pattern=r"^(flight_hours|maneuvers|scenarios|assessments|streak|score)$",
    )
    threshold: float = Field(default=0, ge=0)


class BadgeCreate(BaseModel):
    """Request payload for creating a badge definition."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(..., min_length=1, max_length=2000)
    icon: str | None = Field(default=None, max_length=255)
    criteria: BadgeCriteria
    category: str = Field(
        ...,
        pattern=r"^(flight|communication|decision|procedure|safety|custom)$",
    )
    tier: str = Field(
        ...,
        pattern=r"^(bronze|silver|gold|platinum|custom)$",
    )
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


# ── UserBadge ────────────────────────────────────────────────────


class UserBadgeRead(BaseModel):
    """Schema returned when reading a user's earned badge."""

    id: uuid.UUID
    user_id: uuid.UUID
    badge_id: uuid.UUID
    earned_at: datetime
    extra_data: dict[str, Any]

    model_config = {"from_attributes": True}


# ── Leaderboard ──────────────────────────────────────────────────


class LeaderboardEntryRead(BaseModel):
    """A single entry within a leaderboard snapshot."""

    user_id: uuid.UUID
    display_name: str
    score: float
    rank: int
    metrics: dict[str, Any] = {}


class LeaderboardSnapshotRead(BaseModel):
    """Schema returned when reading a leaderboard snapshot."""

    id: uuid.UUID
    org_id: uuid.UUID | None = None
    period: str
    data: list[dict[str, Any]]
    generated_at: datetime

    model_config = {"from_attributes": True}


class BadgeProgressRead(BaseModel):
    """Schema for badge progress towards earning."""

    badge_id: str
    badge_name: str
    badge_tier: str
    current_value: float
    target_value: float
    progress_percent: float
