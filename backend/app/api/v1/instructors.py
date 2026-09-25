"""Instructor profile API routes.

- ``GET  /me/profile``         — own instructor profile
- ``PUT  /me/profile``         — update own instructor profile
- ``GET  /{user_id}/profile``  — get another instructor's profile
- ``GET  /``                   — search instructors
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.instructor_repository import InstructorRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import get_authenticated_user, get_org_id
from app.models.assessment import KnowledgeAssessment
from app.models.seat import Seat
from app.models.student_stats import StudentStats
from app.models.training_session import TrainingSession
from app.models.user import User
from app.models.voice_log import VoiceLog
from app.schemas.instructor import (
    InstructorProfileRead,
    InstructorProfileUpdate,
    InstructorStatsRead,
    InstructorStudentRead,
    RecentSessionRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instructors", tags=["Instructors"])

instructor_repo = InstructorRepository()


@router.get("/me/profile", response_model=InstructorProfileRead)
async def get_my_profile(
    user: RequireInstructor,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> InstructorProfileRead:
    """Get the current user's instructor profile.

    Requires instructor role or higher.  Returns 404 if no profile
    has been created yet.
    """
    profile = await instructor_repo.get_profile(db, local_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor profile not found. Create one with PUT /me/profile.",
        )
    return profile  # type: ignore[return-value]


@router.put("/me/profile", response_model=InstructorProfileRead)
async def update_my_profile(
    data: InstructorProfileUpdate,
    user: RequireInstructor,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> InstructorProfileRead:
    """Create or update the current user's instructor profile.

    Requires instructor role or higher.  This is an upsert — the
    profile is created if it does not exist, or updated if it does.
    Only fields present in the request body are updated.
    """
    update_data = data.model_dump(exclude_unset=True)
    profile = await instructor_repo.create_or_update_profile(
        db, local_user.id, update_data
    )
    return profile  # type: ignore[return-value]


@router.get("/{user_id}/profile", response_model=InstructorProfileRead)
async def get_instructor_profile(
    user_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> InstructorProfileRead:
    """Get the instructor profile for a given user.

    Accessible to any authenticated user (for student-instructor
    matching).
    """
    profile = await instructor_repo.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instructor profile for user {user_id} not found",
        )
    return profile  # type: ignore[return-value]


@router.get("/", response_model=list[InstructorProfileRead])
async def search_instructors(
    _user: CurrentUser,
    org_id: uuid.UUID | None = Depends(get_org_id),
    specialization: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[InstructorProfileRead]:
    """Search instructor profiles.

    Results can be filtered by organisation (defaults to the
    user's org) and by specialization keyword.
    """
    profiles = await instructor_repo.search_instructors(
        db,
        org_id=org_id,
        specialization=specialization,
        limit=limit,
        offset=offset,
    )
    return profiles  # type: ignore[return-value]


# ── Students ───────────────────────────────────────────────────────


@router.get("/students", response_model=list[InstructorStudentRead])
async def get_my_students(
    user: RequireInstructor,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> list:
    """List students for the current instructor."""
    from app.models.training_session import TrainingSession
    from app.models.voice_log import VoiceLog
    from app.schemas.instructor import InstructorStudentRead

    result = await db.execute(
        select(User)
        .join(Seat, Seat.user_id == User.id)
        .where(
            Seat.organization_id == org_id,
            Seat.role == "student",
            Seat.is_active.is_(True),
        )
    )
    students = list(result.scalars().all())
    out = []
    for s in students:
        flight_hours = await db.scalar(
            select(func.coalesce(func.sum(VoiceLog.audio_duration_ms), 0) / 3600000.0)
            .join(TrainingSession, TrainingSession.id == VoiceLog.session_id)
            .where(TrainingSession.user_id == s.id)
        ) or 0.0
        completed = await db.scalar(
            select(func.count(TrainingSession.id)).where(
                TrainingSession.user_id == s.id,
                TrainingSession.status == "completed",
            )
        ) or 0
        avg_score = await db.scalar(
            select(func.avg(StudentStats.overall_score))
            .where(StudentStats.user_id == s.id)
        )
        out.append({
            "id": str(s.id),
            "user_id": str(s.id),
            "display_name": s.display_name,
            "email": s.email,
            "flight_hours": round(flight_hours, 1),
            "scenarios_completed": completed,
            "overall_score": round(float(avg_score or 0), 1),
            "last_active": None,
        })
    return out


@router.get("/students/{student_id}", response_model=InstructorStudentRead)
async def get_student_detail(
    student_id: uuid.UUID,
    user: RequireInstructor,
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get detailed info for a specific student."""
    from app.models.training_session import TrainingSession

    s = await db.get(User, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found")

    seat = await db.scalar(
        select(Seat).where(
            Seat.user_id == student_id,
            Seat.organization_id == org_id,
            Seat.role == "student",
        )
    )
    if seat is None:
        raise HTTPException(status_code=404, detail="Student not in your organization")

    flight_hours = await db.scalar(
        select(func.coalesce(func.sum(VoiceLog.audio_duration_ms), 0) / 3600000.0)
        .join(TrainingSession, TrainingSession.id == VoiceLog.session_id)
        .where(TrainingSession.user_id == s.id)
    ) or 0.0

    completed = await db.scalar(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.user_id == s.id,
            TrainingSession.status == "completed",
        )
    ) or 0

    avg_score = await db.scalar(
        select(func.avg(StudentStats.overall_score))
        .where(StudentStats.user_id == s.id)
    )

    recent = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.user_id == s.id)
        .order_by(TrainingSession.started_at.desc().nullslast())
        .limit(10)
    )
    recent_sessions = []
    for rs in recent.scalars().all():
        recent_sessions.append({
            "id": str(rs.id),
            "scenario_name": rs.scenario.name if rs.scenario else "Unknown",
            "score": 0,
            "status": rs.status,
            "started_at": rs.started_at.isoformat() if rs.started_at else None,
            "ended_at": rs.ended_at.isoformat() if rs.ended_at else None,
            "duration_minutes": 0,
        })

    return {
        "id": str(s.id),
        "user_id": str(s.id),
        "display_name": s.display_name,
        "email": s.email,
        "flight_hours": round(float(flight_hours), 1),
        "scenarios_completed": completed,
        "overall_score": round(float(avg_score or 0), 1),
        "last_active": None,
        "recent_sessions": recent_sessions,
    }


# ── Stats ──────────────────────────────────────────────────────────


@router.get("/stats", response_model=InstructorStatsRead)
async def get_my_instructor_stats(
    user: RequireInstructor,
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get statistics for the current instructor."""
    from app.models.training_session import TrainingSession
    from app.schemas.instructor import InstructorStatsRead

    student_count = await db.scalar(
        select(func.count(Seat.id)).where(
            Seat.organization_id == org_id,
            Seat.role == "student",
            Seat.is_active.is_(True),
        )
    ) or 0

    active_sessions = await db.scalar(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.org_id == org_id,
            TrainingSession.status == "active",
        )
    ) or 0

    avg_score = await db.scalar(
        select(func.avg(StudentStats.overall_score)).where(
            StudentStats.user_id.in_(
                select(Seat.user_id).where(
                    Seat.organization_id == org_id,
                    Seat.role == "student",
                )
            )
        )
    )

    assessments = await db.scalar(
        select(func.count(KnowledgeAssessment.id)).where(
            KnowledgeAssessment.org_id == org_id,
        )
    ) or 0

    return {
        "total_students": student_count,
        "active_sessions": active_sessions,
        "average_student_score": round(float(avg_score or 0), 1),
        "assessments_created": assessments,
    }


# ── Recent Sessions ────────────────────────────────────────────────


@router.get("/sessions/recent", response_model=list[RecentSessionRead])
async def get_recent_instructor_sessions(
    user: RequireInstructor,
    org_id: uuid.UUID | None = Depends(get_org_id),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> list:
    """Get recent training sessions for the instructor's org."""
    from app.models.training_session import TrainingSession
    from app.schemas.instructor import RecentSessionRead

    result = await db.execute(
        select(TrainingSession)
        .options(selectinload(TrainingSession.user), selectinload(TrainingSession.scenario))
        .where(TrainingSession.org_id == org_id)
        .order_by(TrainingSession.started_at.desc().nullslast())
        .limit(limit)
    )
    out = []
    for ts in result.scalars().all():
        out.append({
            "id": str(ts.id),
            "student_name": ts.user.display_name if ts.user else "Unknown",
            "student_id": str(ts.user_id) if ts.user_id else None,
            "scenario_name": ts.scenario.name if ts.scenario else "Unknown",
            "score": 0,
            "status": ts.status,
            "started_at": ts.started_at.isoformat() if ts.started_at else None,
            "duration_minutes": 0,
        })
    return out
