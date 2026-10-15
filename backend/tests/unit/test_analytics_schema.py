"""Unit tests for the analytics API schemas."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.analytics import (
    AnalyticsOverview,
    LeaderboardEntry,
    OrganizationLeaderboardEntry,
    PopularScenario,
    SessionsByDay,
)


class TestLeaderboardEntry:
    def test_accepts_full_entry(self) -> None:
        entry = LeaderboardEntry(
            user_id=uuid.uuid4(),
            display_name="Ace",
            email="ace@example.com",
            completed_sessions=12,
            total_voice_logs=40,
            total_duration_ms=3_600_000,
            avg_session_duration_ms=300000.0,
        )
        assert entry.completed_sessions == 12
        assert isinstance(entry.avg_session_duration_ms, float)

    def test_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            LeaderboardEntry(user_id=uuid.uuid4())


class TestSessionsByDay:
    def test_parses_iso_date(self) -> None:
        entry = SessionsByDay(date="2024-03-01", count=4)
        assert entry.date == date(2024, 3, 1)

    def test_rejects_invalid_date(self) -> None:
        with pytest.raises(ValidationError, match="date"):
            SessionsByDay(date="not-a-date", count=1)


class TestAnalyticsOverview:
    def test_holds_series_and_scenarios(self) -> None:
        overview = AnalyticsOverview(
            total_sessions=10,
            completed_sessions=8,
            active_sessions=2,
            total_scenarios=5,
            total_users=3,
            sessions_by_day=[SessionsByDay(date="2024-03-01", count=4)],
            popular_scenarios=[
                PopularScenario(scenario_id=1, name="Pattern", session_count=6)
            ],
        )
        assert overview.sessions_by_day[0].count == 4
        assert overview.popular_scenarios[0].session_count == 6

    def test_series_are_required(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsOverview(
                total_sessions=0,
                completed_sessions=0,
                active_sessions=0,
                total_scenarios=0,
                total_users=0,
            )


class TestOrganizationLeaderboardEntry:
    def test_accepts_full_row(self) -> None:
        entry = OrganizationLeaderboardEntry(
            organization_id=uuid.uuid4(),
            organization_name="Sky",
            organization_slug="sky",
            is_active=True,
            total_sessions=20,
            completed_sessions=15,
            active_sessions=5,
            active_seats=8,
            completion_rate=0.75,
        )
        assert entry.completion_rate == pytest.approx(0.75)
