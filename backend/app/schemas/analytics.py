"""Pydantic schemas for analytics API endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    """A single entry in the organization leaderboard.

    Users are ranked by the number of completed training sessions.
    Aggregate voice-log statistics provide additional context.
    """

    user_id: uuid.UUID
    display_name: str
    email: str
    completed_sessions: int
    total_voice_logs: int
    total_duration_ms: int
    avg_session_duration_ms: float


class SessionsByDay(BaseModel):
    """Session count for a single calendar day."""

    date: date
    count: int


class PopularScenario(BaseModel):
    """A scenario with its session count for popularity ranking."""

    scenario_id: int
    name: str
    session_count: int


class AnalyticsOverview(BaseModel):
    """Organization-level analytics overview.

    Contains aggregate counters, a 30-day time series, and a list of the
    most popular scenarios.
    """

    total_sessions: int
    completed_sessions: int
    active_sessions: int
    total_scenarios: int
    total_users: int
    sessions_by_day: list[SessionsByDay]
    popular_scenarios: list[PopularScenario]


class OrganizationLeaderboardEntry(BaseModel):
    """Platform-level leaderboard row for organization progress."""

    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    is_active: bool
    total_sessions: int
    completed_sessions: int
    active_sessions: int
    active_seats: int
    completion_rate: float
