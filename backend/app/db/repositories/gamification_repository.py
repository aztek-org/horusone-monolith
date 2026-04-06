"""Repository for gamification — badges, awards, and leaderboards."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import Badge, LeaderboardSnapshot, UserBadge
from app.models.student_stats import StudentStats

logger = logging.getLogger(__name__)


class GamificationRepository:
    """Data-access layer for the badge and leaderboard systems."""

    # ── Badges ─────────────────────────────────────────────────────

    async def get_all_badges(
        self,
        db: AsyncSession,
        category: str | None = None,
        org_id: uuid.UUID | None = None,
        include_all: bool = False,
    ) -> list[Badge]:
        """Get all badge definitions, optionally filtered by category.

        Args:
            db: Async database session.
            category: Optional category filter (e.g. "flight", "communication").
            org_id: Organization scope for org-specific badges.
            include_all: When True, bypass org scoping (platform-admin use).

        Returns:
            List of active Badge rows ordered by sort_order.
        """
        query = select(Badge).where(Badge.is_active.is_(True))
        if not include_all:
            if org_id is None:
                query = query.where(Badge.org_id.is_(None))
            else:
                query = query.where((Badge.org_id == org_id) | Badge.org_id.is_(None))
        if category:
            query = query.where(Badge.category == category)
        query = query.order_by(Badge.sort_order, Badge.name)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_badge_by_slug(
        self,
        db: AsyncSession,
        slug: str,
        org_id: uuid.UUID | None,
    ) -> Badge | None:
        """Get a badge by slug within an organization scope."""
        query = select(Badge).where(Badge.slug == slug)
        if org_id is None:
            query = query.where(Badge.org_id.is_(None))
        else:
            query = query.where(Badge.org_id == org_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def create_badge(
        self,
        db: AsyncSession,
        *,
        payload: dict[str, Any],
        org_id: uuid.UUID | None,
    ) -> Badge:
        """Create a badge definition."""
        badge = Badge(**payload, org_id=org_id)
        db.add(badge)
        await db.flush()
        await db.refresh(badge)
        return badge

    async def get_user_badges(
        self, db: AsyncSession, user_id: uuid.UUID
    ) -> list[UserBadge]:
        """Get all badges earned by a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            List of UserBadge rows ordered by earned_at.
        """
        result = await db.execute(
            select(UserBadge)
            .where(UserBadge.user_id == user_id)
            .order_by(UserBadge.earned_at.desc())
        )
        return list(result.scalars().all())

    async def award_badge(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        badge_id: uuid.UUID,
        metadata: dict[str, Any] | None = None,
    ) -> UserBadge | None:
        """Award a badge to a user (idempotent — skips if already earned).

        Args:
            db: Async database session.
            user_id: UUID of the user.
            badge_id: UUID of the badge to award.
            metadata: Optional extra data about the award.

        Returns:
            The UserBadge if newly created, or None if already exists.
        """
        # Check for existing award
        existing = await db.execute(
            select(UserBadge).where(
                UserBadge.user_id == user_id,
                UserBadge.badge_id == badge_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "Badge %s already awarded to user %s — skipping",
                badge_id, user_id,
            )
            return None

        award = UserBadge(
            user_id=user_id,
            badge_id=badge_id,
            extra_data=metadata or {},
        )
        db.add(award)
        await db.flush()
        await db.refresh(award)
        logger.info("Awarded badge %s to user %s", badge_id, user_id)
        return award

    async def check_and_award_badges(
        self, db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID | None = None
    ) -> list[UserBadge]:
        """Evaluate all badge criteria and award any that are newly met.

        This is a simplified rule engine.  Each badge's ``criteria`` JSONB
        is expected to contain a ``type`` key indicating the rule, e.g.
        ``{"type": "flight_hours", "threshold": 10}``.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            List of newly awarded UserBadge rows.
        """
        # Load user stats
        stats_result = await db.execute(
            select(StudentStats).where(StudentStats.user_id == user_id)
        )
        stats = stats_result.scalar_one_or_none()
        if stats is None:
            return []

        # Load all active badges
        badges = await self.get_all_badges(db, org_id=org_id)
        awarded: list[UserBadge] = []

        for badge in badges:
            criteria = badge.criteria or {}
            rule_type = criteria.get("type")
            threshold = criteria.get("threshold", 0)

            earned = False
            if rule_type == "flight_hours":
                earned = stats.total_flight_hours >= threshold
            elif rule_type == "maneuvers":
                earned = stats.total_maneuvers >= threshold
            elif rule_type == "scenarios":
                earned = stats.total_scenarios_completed >= threshold
            elif rule_type == "assessments":
                earned = stats.total_assessments >= threshold
            elif rule_type == "streak":
                earned = stats.best_streak >= threshold
            elif rule_type == "score":
                earned = stats.overall_score >= threshold
            # Add more rule types as needed

            if earned:
                result = await self.award_badge(db, user_id, badge.id)
                if result is not None:
                    awarded.append(result)

        return awarded

    # ── Leaderboard ────────────────────────────────────────────────

    async def get_leaderboard(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None = None,
        period: str = "weekly",
        limit: int = 20,
    ) -> LeaderboardSnapshot | None:
        """Get the most recent leaderboard snapshot for a period.

        Args:
            db: Async database session.
            org_id: Optional organisation filter.
            period: Period key (daily, weekly, monthly, all-time).
            limit: Not used for snapshot retrieval (data is pre-ranked).

        Returns:
            The most recent LeaderboardSnapshot, or None.
        """
        query = (
            select(LeaderboardSnapshot)
            .where(LeaderboardSnapshot.period == period)
        )
        if org_id is not None:
            query = query.where(LeaderboardSnapshot.org_id == org_id)
        else:
            query = query.where(LeaderboardSnapshot.org_id.is_(None))

        result = await db.execute(
            query.order_by(LeaderboardSnapshot.generated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def generate_leaderboard_snapshot(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None = None,
        period: str = "weekly",
    ) -> LeaderboardSnapshot:
        """Generate a new leaderboard snapshot from current student stats.

        Builds a ranked list of users by overall_score within the
        organisation scope.

        Args:
            db: Async database session.
            org_id: Optional organisation scope.
            period: Period key for the snapshot.

        Returns:
            The created LeaderboardSnapshot.
        """
        from app.models.seat import Seat
        from app.models.user import User

        # Build query for stats — optionally scoped by org
        query = (
            select(StudentStats, User.display_name)
            .join(User, User.id == StudentStats.user_id)
        )
        if org_id is not None:
            query = query.join(
                Seat, Seat.user_id == User.id
            ).where(
                Seat.organization_id == org_id,
                Seat.is_active.is_(True),
            )

        query = query.order_by(StudentStats.overall_score.desc()).limit(100)
        result = await db.execute(query)
        rows = result.all()

        entries: list[dict[str, Any]] = []
        for rank, (stats, display_name) in enumerate(rows, start=1):
            entries.append({
                "user_id": str(stats.user_id),
                "display_name": display_name,
                "score": stats.overall_score,
                "rank": rank,
                "metrics": {
                    "flight_hours": stats.total_flight_hours,
                    "maneuvers": stats.total_maneuvers,
                    "scenarios": stats.total_scenarios_completed,
                },
            })

        snapshot = LeaderboardSnapshot(
            org_id=org_id,
            period=period,
            data=entries,
        )
        db.add(snapshot)
        await db.flush()
        await db.refresh(snapshot)
        logger.info(
            "Generated %s leaderboard snapshot (org=%s, %d entries)",
            period, org_id, len(entries),
        )
        return snapshot
