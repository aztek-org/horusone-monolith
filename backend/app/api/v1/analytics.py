"""Analytics API routes for leaderboard and overview dashboards.

Both endpoints require the *instructor* role or higher and are scoped
to a specific organization via the ``org_id`` query parameter.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import is_platform_admin, verify_org_access
from app.db.repositories.organization_repo import OrganizationRepository
from app.db.session import get_db_session
from app.middleware.auth import RequireInstructor
from app.models.scenario import Scenario
from app.models.seat import Seat
from app.models.training_session import TrainingSession
from app.models.user import User
from app.models.voice_log import VoiceLog
from app.schemas.analytics import (
    AnalyticsOverview,
    LeaderboardEntry,
    PopularScenario,
    SessionsByDay,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])

org_repo = OrganizationRepository()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _validate_org(
    org_id: uuid.UUID,
    user: RequireInstructor,
    session: AsyncSession,
) -> None:
    """Verify the organization exists and the user can access it.

    Args:
        org_id: Organization UUID from the query parameter.
        user: The authenticated instructor/admin.
        session: Active database session.

    Raises:
        HTTPException: 404 if org does not exist, 403 if access denied.
    """
    if not is_platform_admin(user):
        verify_org_access(user, org_id)

    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    user: RequireInstructor,
    org_id: uuid.UUID = Query(..., description="Organization to get leaderboard for"),
    limit: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> list[LeaderboardEntry]:
    """Get the leaderboard of top users by completed sessions.

    Requires *instructor* role or higher.  Users are ranked by the
    number of completed training sessions within the specified
    organization.  Includes aggregate voice-log statistics.
    """
    await _validate_org(org_id, user, session)

    completed_count = func.count(distinct(TrainingSession.id)).filter(
        TrainingSession.status == "completed"
    )
    voice_log_count = func.count(distinct(VoiceLog.id))
    total_duration = func.coalesce(func.sum(VoiceLog.audio_duration_ms), 0)

    query = (
        select(
            User.id.label("user_id"),
            User.display_name,
            User.email,
            completed_count.label("completed_sessions"),
            voice_log_count.label("total_voice_logs"),
            total_duration.label("total_duration_ms"),
        )
        .join(TrainingSession, TrainingSession.user_id == User.id)
        .outerjoin(VoiceLog, VoiceLog.session_id == TrainingSession.id)
        .where(TrainingSession.org_id == org_id)
        .group_by(User.id, User.display_name, User.email)
        .order_by(completed_count.desc())
        .limit(limit)
    )

    result = await session.execute(query)
    return [
        LeaderboardEntry(
            user_id=row.user_id,
            display_name=row.display_name,
            email=row.email,
            completed_sessions=row.completed_sessions,
            total_voice_logs=row.total_voice_logs,
            total_duration_ms=row.total_duration_ms,
            avg_session_duration_ms=(
                row.total_duration_ms / row.completed_sessions
                if row.completed_sessions > 0
                else 0.0
            ),
        )
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    user: RequireInstructor,
    org_id: uuid.UUID = Query(..., description="Organization to get overview for"),
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsOverview:
    """Get analytics overview for an organization.

    Requires *instructor* role or higher.  Returns aggregate statistics,
    a 30-day session time series, and the top-5 most popular scenarios.
    """
    await _validate_org(org_id, user, session)

    # ── Aggregate session counts ───────────────────────────────────
    total_sessions = (
        await session.scalar(
            select(func.count(TrainingSession.id)).where(TrainingSession.org_id == org_id)
        )
        or 0
    )
    completed_sessions = (
        await session.scalar(
            select(func.count(TrainingSession.id)).where(
                TrainingSession.org_id == org_id,
                TrainingSession.status == "completed",
            )
        )
        or 0
    )
    active_sessions = (
        await session.scalar(
            select(func.count(TrainingSession.id)).where(
                TrainingSession.org_id == org_id,
                TrainingSession.status == "active",
            )
        )
        or 0
    )

    # ── Entity totals ──────────────────────────────────────────────
    total_scenarios = (
        await session.scalar(select(func.count(Scenario.id)).where(Scenario.org_id == org_id)) or 0
    )
    total_users = (
        await session.scalar(
            select(func.count(Seat.id)).where(
                Seat.organization_id == org_id, Seat.is_active.is_(True)
            )
        )
        or 0
    )

    # ── Sessions by day (last 30 days) ─────────────────────────────
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_result = await session.execute(
        select(
            cast(TrainingSession.started_at, Date).label("day"),
            func.count(TrainingSession.id).label("count"),
        )
        .where(
            TrainingSession.org_id == org_id,
            TrainingSession.started_at >= thirty_days_ago,
        )
        .group_by(cast(TrainingSession.started_at, Date))
        .order_by(cast(TrainingSession.started_at, Date))
    )
    sessions_by_day = [SessionsByDay(date=row.day, count=row.count) for row in daily_result.all()]

    # ── Popular scenarios (top 5 by session count) ─────────────────
    popular_result = await session.execute(
        select(
            Scenario.id.label("scenario_id"),
            Scenario.name,
            func.count(TrainingSession.id).label("session_count"),
        )
        .join(TrainingSession, TrainingSession.scenario_id == Scenario.id)
        .where(TrainingSession.org_id == org_id)
        .group_by(Scenario.id, Scenario.name)
        .order_by(func.count(TrainingSession.id).desc())
        .limit(5)
    )
    popular_scenarios = [
        PopularScenario(
            scenario_id=row.scenario_id,
            name=row.name,
            session_count=row.session_count,
        )
        for row in popular_result.all()
    ]

    return AnalyticsOverview(
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
        active_sessions=active_sessions,
        total_scenarios=total_scenarios,
        total_users=total_users,
        sessions_by_day=sessions_by_day,
        popular_scenarios=popular_scenarios,
    )
