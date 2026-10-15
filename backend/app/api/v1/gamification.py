"""Gamification API routes — badges, awards, and leaderboards.

- ``GET  /badges``          — all available badges
- ``GET  /me/badges``       — current user's earned badges
- ``GET  /leaderboard``     — leaderboard snapshot
- ``POST /check``           — trigger badge evaluation for current user
"""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import is_platform_admin
from app.db.repositories.gamification_repository import GamificationRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.gamification import (
    BadgeCreate,
    BadgeProgressRead,
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
    user: CurrentUser,
    category: str | None = Query(default=None),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[BadgeRead]:
    """Get all available badge definitions.

    Optionally filter by ``category`` (e.g. "flight", "communication").
    """
    badges = await gamification_repo.get_all_badges(
        db,
        category=category,
        org_id=org_id,
        include_all=is_platform_admin(user),
    )
    return badges  # type: ignore[return-value]


@router.post("/badges", response_model=BadgeRead, status_code=status.HTTP_201_CREATED)
async def create_badge(
    data: BadgeCreate,
    user: RequireInstructor,
    _seat: RequireActiveSeat,
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> BadgeRead:
    """Create a badge definition for the current organization context."""
    target_org_id = None if is_platform_admin(user) else org_id
    if target_org_id is None and not is_platform_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context is required to create badges",
        )

    slug = data.slug or _slugify_badge_name(data.name)
    existing = await gamification_repo.get_badge_by_slug(db, slug, target_org_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Badge with slug '{slug}' already exists",
        )

    badge = await gamification_repo.create_badge(
        db,
        payload={
            "name": data.name.strip(),
            "slug": slug,
            "description": data.description.strip(),
            "icon": data.icon,
            "criteria": data.criteria.model_dump(),
            "category": data.category,
            "tier": data.tier,
            "sort_order": data.sort_order,
            "is_active": data.is_active,
        },
        org_id=target_org_id,
    )
    logger.info("Created badge %s (org=%s)", badge.slug, target_org_id)
    return badge  # type: ignore[return-value]


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
    org_id: uuid.UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserBadgeRead]:
    """Trigger badge evaluation for the current user.

    Evaluates all active badge criteria against the user's current
    stats and awards any newly earned badges.  Returns the list of
    badges awarded in this evaluation.
    """
    awarded = await gamification_repo.check_and_award_badges(db, local_user.id, org_id=org_id)
    logger.info(
        "Badge check for user %s: %d new badges awarded",
        local_user.id,
        len(awarded),
    )
    return awarded  # type: ignore[return-value]


# ── Badge progress ─────────────────────────────────────────────────


@router.get("/me/badges/progress", response_model=list[BadgeProgressRead])
async def get_badge_progress(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[BadgeProgressRead]:
    """Get progress towards all active badges for the current user."""
    from app.models.gamification import Badge
    from app.models.student_stats import StudentStats

    stats = await db.scalar(select(StudentStats).where(StudentStats.user_id == local_user.id))

    badges_result = await db.execute(
        select(Badge)
        .where(
            Badge.is_active.is_(True),
            (Badge.org_id == org_id) | (Badge.org_id.is_(None)),
        )
        .order_by(Badge.sort_order)
    )
    badges = list(badges_result.scalars().all())

    progress = []
    for badge in badges:
        criteria = badge.criteria or {}
        criteria_type = criteria.get("type", "scenarios")
        threshold = float(criteria.get("threshold", 1))

        current = 0.0
        if stats:
            if criteria_type == "flight_hours":
                current = float(stats.total_flight_hours or 0)
            elif criteria_type == "scenarios":
                current = float(stats.total_sessions or 0)
            elif criteria_type == "assessments":
                current = float(stats.assessments_passed or 0)
            elif criteria_type == "score":
                current = float(stats.average_score or 0)
            elif criteria_type == "streak":
                current = float(stats.current_streak or 0)

        pct = min(round((current / threshold) * 100, 1) if threshold > 0 else 100.0, 100.0)
        progress.append(
            BadgeProgressRead(
                badge_id=str(badge.id),
                badge_name=badge.name,
                badge_tier=badge.tier,
                current_value=current,
                target_value=threshold,
                progress_percent=pct,
            )
        )

    return progress


def _slugify_badge_name(name: str) -> str:
    """Create a slug from badge name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug or f"badge-{uuid.uuid4().hex[:8]}"
