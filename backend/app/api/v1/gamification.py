"""Gamification API routes — badges, awards, and leaderboards.

- ``GET  /badges``          — all available badges
- ``GET  /me/badges``       — current user's earned badges
- ``GET  /leaderboard``     — leaderboard snapshot
- ``POST /check``           — trigger badge evaluation for current user
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.gamification_repository import GamificationRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.gamification import (
    BadgeRead,
    LeaderboardSnapshotRead,
    UserBadgeRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gamification", tags=["Gamification"])

gamification_repo = GamificationRepository()


# ── Badges ─────────────────────────────────────────────────────────


@router.get("/badges", response_model=list[BadgeRead])
async def list_badges(
    _user: CurrentUser,
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[BadgeRead]:
    """Get all available badge definitions.

    Optionally filter by ``category`` (e.g. "flight", "communication").
    """
    badges = await gamification_repo.get_all_badges(db, category)
    return badges  # type: ignore[return-value]


@router.get("/me/badges", response_model=list[UserBadgeRead])
async def get_my_badges(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserBadgeRead]:
    """Get all badges earned by the current user."""
    badges = await gamification_repo.get_user_badges(db, local_user.id)
    return badges  # type: ignore[return-value]


# ── Leaderboard ────────────────────────────────────────────────────


@router.get("/leaderboard", response_model=LeaderboardSnapshotRead | None)
async def get_leaderboard(
    _user: CurrentUser,
    period: str = Query(default="weekly", pattern=r"^(daily|weekly|monthly|all-time)$"),
    org_id: uuid.UUID | None = Depends(get_org_id),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> LeaderboardSnapshotRead | None:
    """Get the most recent leaderboard snapshot.

    Returns the latest pre-computed snapshot for the given period
    and organisation scope.  Returns ``null`` if no snapshot exists
    yet.
    """
    snapshot = await gamification_repo.get_leaderboard(
        db, org_id=org_id, period=period, limit=limit
    )
    return snapshot  # type: ignore[return-value]


# ── Badge evaluation trigger ───────────────────────────────────────


@router.post("/check", response_model=list[UserBadgeRead])
async def check_badges(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserBadgeRead]:
    """Trigger badge evaluation for the current user.

    Evaluates all active badge criteria against the user's current
    stats and awards any newly earned badges.  Returns the list of
    badges awarded in this evaluation.
    """
    awarded = await gamification_repo.check_and_award_badges(
        db, local_user.id
    )
    logger.info(
        "Badge check for user %s: %d new badges awarded",
        local_user.id, len(awarded),
    )
    return awarded  # type: ignore[return-value]
