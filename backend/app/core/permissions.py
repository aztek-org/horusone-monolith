"""Permission and authorization helpers for RBAC enforcement.

Provides pure-function helpers for checking user roles and organization
access.  These are meant to be called inside route handlers — they are
*not* FastAPI dependencies themselves.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.middleware.auth import TokenUser


def is_platform_admin(user: TokenUser) -> bool:
    """Check if the user has the platform-admin role.

    Args:
        user: Authenticated user extracted from JWT.

    Returns:
        True if the user is a platform administrator.
    """
    return "platform-admin" in user.roles


def has_role(user: TokenUser, *roles: str) -> bool:
    """Check if the user has at least one of the specified roles.

    Args:
        user: Authenticated user extracted from JWT.
        roles: One or more role names to check.

    Returns:
        True if the user holds any of the given roles.
    """
    return any(role in user.roles for role in roles)


def get_user_org_id(user: TokenUser) -> UUID | None:
    """Get the user's organization_id from JWT claims.

    Args:
        user: Authenticated user extracted from JWT.

    Returns:
        The organization UUID, or ``None`` if not present.
    """
    if user.organization_id:
        return UUID(user.organization_id)
    return None


def can_access_org(user: TokenUser, org_id: UUID) -> bool:
    """Check if a user can access a specific organization.

    Platform admins can access any organization.  Other users can only
    access their own organization (as declared in the JWT).

    Args:
        user: Authenticated user extracted from JWT.
        org_id: The organization UUID to check access for.

    Returns:
        True if the user is authorized to access the organization.
    """
    if is_platform_admin(user):
        return True
    user_org = get_user_org_id(user)
    return user_org is not None and user_org == org_id


def verify_org_access(user: TokenUser, org_id: UUID) -> None:
    """Assert the user can access the given organization, or raise 403.

    Args:
        user: Authenticated user extracted from JWT.
        org_id: The organization UUID to verify access for.

    Raises:
        HTTPException: 403 Forbidden if the user cannot access the org.
    """
    if not can_access_org(user, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization",
        )
