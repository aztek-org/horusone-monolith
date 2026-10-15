"""Student statistics API routes.

- ``GET  /me``                           — current user's stats summary
- ``GET  /{user_id}``                    — stats for another user (instructor+)
- ``GET  /me/flight-hours``              — paginated flight hours
- ``GET  /me/maneuvers``                 — paginated maneuver logs
- ``GET  /me/assessments``               — paginated assessment results
- ``GET  /me/transcript/{session_id}``   — voice log transcript for a session
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import has_role, is_platform_admin
from app.db.repositories.assessment_repository import AssessmentRepository
from app.db.repositories.student_stats_repository import StudentStatsRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.assessment import AssessmentResultRead
from app.schemas.student_stats import FlightHourLogRead, ManeuverLogRead, StudentStatsRead
from app.schemas.voice_log import VoiceLogResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stats", tags=["Student Statistics"])

stats_repo = StudentStatsRepository()
assessment_repo = AssessmentRepository()


@router.get("/me", response_model=StudentStatsRead)
async def get_my_stats(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudentStatsRead:
    """Get the current user's aggregated statistics summary.

    Requires an active seat.
    """
    stats = await stats_repo.get_user_stats(db, local_user.id)
    return stats  # type: ignore[return-value]


@router.get(
    "/me/flight-hours",
    response_model=list[FlightHourLogRead],
)
async def get_my_flight_hours(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[FlightHourLogRead]:
    """Get the current user's paginated flight-hour log entries."""
    logs = await stats_repo.get_flight_hours(db, local_user.id, limit, offset)
    return logs  # type: ignore[return-value]


@router.get(
    "/me/maneuvers",
    response_model=list[ManeuverLogRead],
)
async def get_my_maneuvers(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    maneuver_type: str | None = Query(default=None, alias="type", min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[ManeuverLogRead]:
    """Get the current user's paginated maneuver log entries."""
    logs = await stats_repo.get_maneuver_logs(
        db,
        local_user.id,
        limit,
        offset,
        maneuver_type=maneuver_type,
    )
    return logs  # type: ignore[return-value]


@router.get(
    "/me/assessments",
    response_model=list[AssessmentResultRead],
)
async def get_my_assessment_results(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[AssessmentResultRead]:
    """Get the current user's paginated assessment results."""
    results = await assessment_repo.get_user_results(db, local_user.id, limit, offset)
    return results  # type: ignore[return-value]


@router.get(
    "/me/transcript/{session_id}",
    response_model=list[VoiceLogResponse],
)
async def get_session_transcript(
    session_id: int,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[VoiceLogResponse]:
    """Download the voice-log transcript for a training session as JSON.

    The session must belong to the current user, unless the requester
    is an instructor, org-admin, or platform-admin.
    """
    from sqlalchemy import select

    from app.models.training_session import TrainingSession

    # Verify session exists and check ownership
    result = await db.execute(select(TrainingSession).where(TrainingSession.id == session_id))
    session_obj = result.scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Ownership / role check
    if session_obj.user_id != local_user.id:
        if not (is_platform_admin(user) or has_role(user, "instructor", "org-admin")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this session",
            )

    logs = await stats_repo.get_transcript(db, session_id, local_user.id)
    return logs  # type: ignore[return-value]


@router.get("/{user_id}", response_model=StudentStatsRead)
async def get_user_stats(
    user_id: uuid.UUID,
    user: RequireInstructor,
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> StudentStatsRead:
    """Get statistics for a specific user.

    Requires instructor, org-admin, or platform-admin role.
    Non-admin users can only view stats of users within their org.
    """
    if not is_platform_admin(user) and org_id is not None:
        # Verify the target user is in the same org
        from sqlalchemy import select as sa_select

        from app.models.seat import Seat

        seat_result = await db.execute(
            sa_select(Seat).where(
                Seat.user_id == user_id,
                Seat.organization_id == org_id,
                Seat.is_active.is_(True),
            )
        )
        if seat_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not in your organization",
            )

    stats = await stats_repo.get_user_stats(db, user_id)
    return stats  # type: ignore[return-value]
