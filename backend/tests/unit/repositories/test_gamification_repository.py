"""Unit tests for GamificationRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.gamification_repository import GamificationRepository
from app.models.gamification import Badge, LeaderboardSnapshot, UserBadge


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


def _scalars_proxy(rows: list) -> MagicMock:
    proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    proxy.scalars.return_value = scalars_proxy
    return proxy


def _scalar_proxy(value: object) -> MagicMock:
    proxy = MagicMock()
    proxy.scalar_one_or_none.return_value = value
    return proxy


# ── GamificationRepository ─────────────────────────────────────────────


class TestGamificationRepository:
    """Tests for badge, award, and leaderboard queries."""

    @pytest.mark.asyncio
    async def test_get_all_badges_returns_rows(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = GamificationRepository()

        assert await repo.get_all_badges(session) == rows

    @pytest.mark.asyncio
    async def test_get_all_badges_default_scopes_to_shared(self) -> None:
        session = _mock_session_scalars([])
        repo = GamificationRepository()

        await repo.get_all_badges(session)

        query = str(session.execute.await_args.args[0])
        assert "badges.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_get_all_badges_org_scope_or_shared(self) -> None:
        session = _mock_session_scalars([])
        repo = GamificationRepository()

        await repo.get_all_badges(session, org_id=uuid.uuid4())

        query = str(session.execute.await_args.args[0])
        assert "badges.org_id = " in query
        assert "badges.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_get_all_badges_include_all_bypasses_org_scope(self) -> None:
        session = _mock_session_scalars([])
        repo = GamificationRepository()

        await repo.get_all_badges(session, include_all=True)

        query = str(session.execute.await_args.args[0])
        assert "badges.org_id IS NULL" not in query
        assert "badges.org_id = " not in query

    @pytest.mark.asyncio
    async def test_get_all_badges_category_filter(self) -> None:
        session = _mock_session_scalars([])
        repo = GamificationRepository()

        await repo.get_all_badges(session, category="flight")

        query = str(session.execute.await_args.args[0])
        assert "badges.category" in query

    @pytest.mark.asyncio
    async def test_get_badge_by_slug_found(self) -> None:
        badge = MagicMock()
        session = _mock_session(scalar_result=badge)
        repo = GamificationRepository()

        assert await repo.get_badge_by_slug(session, "ace", None) is badge

    @pytest.mark.asyncio
    async def test_get_badge_by_slug_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = GamificationRepository()

        assert await repo.get_badge_by_slug(session, "ace", uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_get_badge_by_slug_none_org_filters_shared(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = GamificationRepository()

        await repo.get_badge_by_slug(session, "ace", None)

        query = str(session.execute.await_args.args[0])
        assert "badges.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_create_badge_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = GamificationRepository()
        org_id = uuid.uuid4()

        result = await repo.create_badge(
            session,
            payload={
                "name": "Ace",
                "slug": "ace",
                "description": "d",
                "category": "flight",
                "tier": "gold",
            },
            org_id=org_id,
        )

        assert isinstance(result, Badge)
        assert result.slug == "ace"
        assert result.org_id == org_id
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_badges_returns_rows(self) -> None:
        rows = [MagicMock()]
        session = _mock_session_scalars(rows)
        repo = GamificationRepository()

        assert await repo.get_user_badges(session, uuid.uuid4()) == rows

    @pytest.mark.asyncio
    async def test_award_badge_existing_returns_none(self) -> None:
        session = _mock_session(scalar_result=MagicMock())
        repo = GamificationRepository()

        assert await repo.award_badge(session, uuid.uuid4(), uuid.uuid4()) is None
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_award_badge_new_returns_user_badge(self) -> None:
        session = _mock_session(scalar_result=None)
        session.add = MagicMock()
        repo = GamificationRepository()
        user_id = uuid.uuid4()
        badge_id = uuid.uuid4()

        result = await repo.award_badge(session, user_id, badge_id, metadata={"why": "test"})

        assert isinstance(result, UserBadge)
        assert result.user_id == user_id
        assert result.badge_id == badge_id
        assert result.extra_data == {"why": "test"}
        session.add.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_check_and_award_badges_no_stats_returns_empty(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = GamificationRepository()

        assert await repo.check_and_award_badges(session, uuid.uuid4()) == []

    @pytest.mark.asyncio
    async def test_check_and_award_badges_awards_earned(self) -> None:
        stats = MagicMock()
        stats.total_flight_hours = 20.0
        badge = MagicMock()
        badge.id = uuid.uuid4()
        badge.criteria = {"type": "flight_hours", "threshold": 10}

        session = AsyncMock()
        session.add = MagicMock()
        session.execute.side_effect = [
            _scalar_proxy(stats),
            _scalars_proxy([badge]),
            _scalar_proxy(None),
        ]
        repo = GamificationRepository()

        awarded = await repo.check_and_award_badges(session, uuid.uuid4())

        assert len(awarded) == 1
        assert isinstance(awarded[0], UserBadge)

    @pytest.mark.asyncio
    async def test_check_and_award_badges_not_earned_returns_empty(self) -> None:
        stats = MagicMock()
        stats.total_flight_hours = 2.0
        badge = MagicMock()
        badge.id = uuid.uuid4()
        badge.criteria = {"type": "flight_hours", "threshold": 10}

        session = AsyncMock()
        session.execute.side_effect = [
            _scalar_proxy(stats),
            _scalars_proxy([badge]),
        ]
        repo = GamificationRepository()

        assert await repo.check_and_award_badges(session, uuid.uuid4()) == []

    @pytest.mark.asyncio
    async def test_get_leaderboard_found(self) -> None:
        snapshot = MagicMock()
        session = _mock_session(scalar_result=snapshot)
        repo = GamificationRepository()

        assert await repo.get_leaderboard(session) is snapshot

    @pytest.mark.asyncio
    async def test_get_leaderboard_org_scope(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = GamificationRepository()

        await repo.get_leaderboard(session, org_id=uuid.uuid4(), period="monthly")

        query = str(session.execute.await_args.args[0])
        assert "leaderboard_snapshots.period" in query
        assert "leaderboard_snapshots.org_id = " in query

    @pytest.mark.asyncio
    async def test_get_leaderboard_shared_scope(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = GamificationRepository()

        await repo.get_leaderboard(session)

        query = str(session.execute.await_args.args[0])
        assert "leaderboard_snapshots.org_id IS NULL" in query

    @pytest.mark.asyncio
    async def test_generate_leaderboard_snapshot_builds_ranked_entries(self) -> None:
        stats_a = MagicMock()
        stats_a.user_id = uuid.uuid4()
        stats_a.overall_score = 95.0
        stats_a.total_flight_hours = 40.0
        stats_a.total_maneuvers = 12
        stats_a.total_scenarios_completed = 5

        result_proxy = MagicMock()
        result_proxy.all.return_value = [(stats_a, "Alice")]
        session = AsyncMock()
        session.add = MagicMock()
        session.execute.return_value = result_proxy
        repo = GamificationRepository()

        snapshot = await repo.generate_leaderboard_snapshot(session, period="weekly")

        assert isinstance(snapshot, LeaderboardSnapshot)
        assert snapshot.period == "weekly"
        assert snapshot.data[0]["rank"] == 1
        assert snapshot.data[0]["display_name"] == "Alice"
        assert snapshot.data[0]["score"] == 95.0
        session.add.assert_called_once_with(snapshot)
