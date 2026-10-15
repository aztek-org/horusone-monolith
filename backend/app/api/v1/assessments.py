"""Knowledge assessment API routes.

- ``GET  /``                — list assessments
- ``GET  /{id}``            — get assessment with questions
- ``POST /``                — create assessment (instructor+)
- ``POST /{id}/submit``     — submit answers and get graded result
- ``GET  /me/results``      — current user's assessment results
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import has_role, is_platform_admin
from app.db.repositories.assessment_repository import AssessmentRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.user import User
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentRead,
    AssessmentResultRead,
    AssessmentSubmission,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assessments", tags=["Assessments"])

assessment_repo = AssessmentRepository()


@router.get("/", response_model=list[AssessmentRead])
async def list_assessments(
    user: CurrentUser,
    org_id: uuid.UUID | None = Depends(get_org_id),
    module_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> list[AssessmentRead]:
    """List available assessments.

    Students only see published assessments.  Instructors and admins
    can see unpublished ones as well.
    """
    # Students only see published assessments
    is_published: bool | None = None
    if not (is_platform_admin(user) or has_role(user, "instructor", "org-admin")):
        is_published = True

    assessments = await assessment_repo.list_assessments(
        db, org_id=org_id, module_id=module_id, is_published=is_published
    )
    return assessments  # type: ignore[return-value]


@router.get("/me/results", response_model=list[AssessmentResultRead])
async def get_my_results(
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[AssessmentResultRead]:
    """Get the current user's assessment results."""
    results = await assessment_repo.get_user_results(db, local_user.id, limit, offset)
    return results  # type: ignore[return-value]


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: uuid.UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> AssessmentRead:
    """Get a single assessment with its questions."""
    assessment = await assessment_repo.get_assessment(db, assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found",
        )
    return assessment  # type: ignore[return-value]


@router.post(
    "/",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    data: AssessmentCreate,
    user: RequireInstructor,
    local_user: User = Depends(get_authenticated_user),
    org_id: uuid.UUID | None = Depends(get_org_id),
    db: AsyncSession = Depends(get_db_session),
) -> AssessmentRead:
    """Create a new knowledge assessment.

    Requires instructor role or higher.  The ``org_id`` from the
    request body is used if provided; otherwise falls back to the
    user's organisation context.
    """
    assessment_data = data.model_dump()
    effective_org = assessment_data.pop("org_id", None) or org_id

    assessment = await assessment_repo.create_assessment(
        db, assessment_data, created_by=local_user.id, org_id=effective_org
    )
    return assessment  # type: ignore[return-value]


@router.post(
    "/{assessment_id}/submit",
    response_model=AssessmentResultRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assessment(
    assessment_id: uuid.UUID,
    data: AssessmentSubmission,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    local_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> AssessmentResultRead:
    """Submit answers for an assessment and receive a graded result.

    The server grades the submission by comparing answers against the
    assessment's question definitions and returns the score and
    pass/fail status.
    """
    try:
        result = await assessment_repo.submit_assessment(
            db,
            user_id=local_user.id,
            assessment_id=assessment_id,
            answers=data.answers,
            time_taken_seconds=data.time_taken_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return result  # type: ignore[return-value]
