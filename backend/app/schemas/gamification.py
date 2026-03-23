"""Pydantic schemas for gamification — badges, awards, leaderboards."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Badge ─────────────────────────────────────────────────────────


class BadgeRead(BaseModel):
    """Schema returned when reading a badge definition."""

    id: uuid.UUID
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
