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
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.instructor_repository import InstructorRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.instructor import (
    InstructorProfileRead,
    InstructorProfileUpdate,
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
