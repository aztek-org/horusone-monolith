"""Training session API routes with RBAC enforcement.

- ``GET  /`` — all authenticated users (role-based filtering)
- ``POST /`` — any authenticated user can start a session
- ``GET  /{session_id}`` — access verified per user / org
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import can_access_org, has_role, is_platform_admin
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, TokenUser
from app.middleware.org_context import RequireActiveSeat, get_authenticated_user, get_org_id
from app.models.training_session import TrainingSession
from app.models.user import User
from app.schemas.training_session import TrainingSessionCreate, TrainingSessionResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("/", response_model=list[TrainingSessionResponse])
async def list_sessions(
    user: CurrentUser,
    org_id: UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> list[TrainingSessionResponse]:
    """List training sessions visible to the current user.

    Platform admins see all sessions.  Instructors and org-admins see
    all sessions within their organization.  Students see only their
    own sessions.
    """
    query = select(TrainingSession)

    if is_platform_admin(user):
        pass  # No filter — full access
    elif has_role(user, "org-admin", "instructor"):
        if org_id:
            query = query.where(TrainingSession.org_id == org_id)
        else:
            # Instructor with no org context — own sessions only
            query = query.where(TrainingSession.user_id == local_user.id)
    else:
        # Students see only their own sessions
        query = query.where(TrainingSession.user_id == local_user.id)

    result = await session.execute(
        query.order_by(TrainingSession.started_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())  # type: ignore[return-value]


@router.post("/", response_model=TrainingSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: TrainingSessionCreate,
    user: CurrentUser,
    _seat: RequireActiveSeat,
    org_id: UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Create a new training session.

    Requires an **active seat** in an organization.  Users without a seat
    can browse scenarios and view stats but cannot start training.
    """
    training_session = TrainingSession(
        **data.model_dump(),
        user_id=local_user.id,
        org_id=org_id,
    )
    session.add(training_session)
    await session.flush()
    await session.refresh(training_session)
    logger.info("Created training session: %s (user=%s)", training_session.id, local_user.id)
    return training_session  # type: ignore[return-value]


@router.get("/{session_id}", response_model=TrainingSessionResponse)
async def get_session(
    session_id: int,
    user: CurrentUser,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrainingSessionResponse:
    """Get a specific training session by ID.

    Users can view their own sessions.  Instructors and org-admins can
    view sessions within their organization.  Platform admins can view
    any session.
    """
    result = await session.execute(
        select(TrainingSession)
        .options(selectinload(TrainingSession.voice_logs))
        .where(TrainingSession.id == session_id)
    )
    training_session = result.scalar_one_or_none()
    if training_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if not _can_view_session(user, local_user, training_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )

    return training_session  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _can_view_session(
    token_user: TokenUser,
    local_user: User,
    training_session: TrainingSession,
) -> bool:
    """Check whether the user can view the given training session.

    Args:
        token_user: JWT token user with roles.
        local_user: Local database User record.
        training_session: The session to check access for.

    Returns:
        True if the user is authorized to view the session.
    """
    # Platform admin — full access
    if is_platform_admin(token_user):
        return True

    # Own session
    if training_session.user_id == local_user.id:
        return True

    # Instructor or org-admin in the same org
    if training_session.org_id and has_role(token_user, "org-admin", "instructor"):
        return can_access_org(token_user, training_session.org_id)

    return False
