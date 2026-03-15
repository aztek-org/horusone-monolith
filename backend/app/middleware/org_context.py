"""Organization-scoped data access dependencies."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.seat_repo import SeatRepository
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser
from app.models.user import User
from app.services.user_sync import sync_user_from_token

logger = logging.getLogger(__name__)

seat_repo = SeatRepository()


async def get_authenticated_user(
    token_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Get or create the local User record for the authenticated request.

    Args:
        token_user: User extracted from JWT.
        session: Database session.

    Returns:
        The User ORM model.
    """
    return await sync_user_from_token(session, token_user)


async def get_org_id(
    token_user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> UUID | None:
    """Extract the active organization ID for the current user.

    Resolution order:
    1. ``organization_id`` claim in JWT (set by Keycloak mapper)
    2. First active seat's organization (fallback for single-org users)

    Platform admins may have no org_id (they access all data).

    Args:
        token_user: User from JWT.
        session: Database session.

    Returns:
        Organization UUID or None for platform admins / standalone users.
    """
    # Platform admins bypass org scoping
    if "platform-admin" in token_user.roles:
        # Still use JWT claim if present, else None (full access)
        if token_user.organization_id:
            return UUID(token_user.organization_id)
        return None

    # Try JWT claim first
    if token_user.organization_id:
        return UUID(token_user.organization_id)

    # Fallback: look up user's seats
    user = await sync_user_from_token(session, token_user)
    seats = await seat_repo.get_user_seats(session, user.id)
    active_seats = [s for s in seats if s.is_active]

    if not active_seats:
        return None

    # Use first active seat's org
    return active_seats[0].organization_id


async def require_org_id(
    org_id: UUID | None = Depends(get_org_id),
) -> UUID:
    """Require that the user has an active organization.

    Args:
        org_id: Resolved organization ID.

    Returns:
        Organization UUID.

    Raises:
        HTTPException: If no organization is associated.
    """
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization associated with your account",
        )
    return org_id
