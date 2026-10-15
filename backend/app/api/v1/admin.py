"""Admin API routes for platform and organization management.

Organization CRUD, seat management, user admin, and platform-wide
statistics are all served from this router under ``/api/v1/admin``.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import get_user_org_id, is_platform_admin, verify_org_access
from app.db.repositories.organization_repo import OrganizationRepository
from app.db.repositories.seat_repo import SeatRepository
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_db_session
from app.middleware.auth import RequireAdmin, RequireOrgAdmin
from app.models.organization import Organization
from app.models.scenario import Scenario
from app.models.seat import Seat
from app.models.training_session import TrainingSession
from app.models.user import User
from app.schemas.admin import (
    AdminStats,
    AdminUserUpdate,
    OrganizationFeaturesResponse,
    OrganizationFeaturesUpdate,
    OrganizationWithStats,
    SeatCreateRequest,
    SeatRoleUpdate,
    SeatWithUser,
    UserWithSeats,
)
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate
from app.schemas.user import UserRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])

org_repo = OrganizationRepository()
seat_repo = SeatRepository()
user_repo = UserRepository()


# ── Organization endpoints ─────────────────────────────────────────


@router.get("/organizations/", response_model=list[OrganizationWithStats])
async def list_organizations(
    user: RequireAdmin,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrganizationWithStats]:
    """List all organizations with aggregated statistics.

    Requires *platform-admin* role.  Returns seat count, active session
    count, and scenario count per organization.
    """
    seat_count_sq = (
        select(func.count(Seat.id))
        .where(Seat.organization_id == Organization.id, Seat.is_active.is_(True))
        .correlate(Organization)
        .scalar_subquery()
    )
    active_sessions_sq = (
        select(func.count(TrainingSession.id))
        .where(
            TrainingSession.org_id == Organization.id,
            TrainingSession.status == "active",
        )
        .correlate(Organization)
        .scalar_subquery()
    )
    scenario_count_sq = (
        select(func.count(Scenario.id))
        .where(Scenario.org_id == Organization.id)
        .correlate(Organization)
        .scalar_subquery()
    )

    query = (
        select(
            Organization,
            seat_count_sq.label("seat_count"),
            active_sessions_sq.label("active_sessions"),
            scenario_count_sq.label("scenario_count"),
        )
        .order_by(Organization.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(query)
    return [
        OrganizationWithStats(
            id=org.id,
            name=org.name,
            slug=org.slug,
            logo_url=org.logo_url,
            is_active=org.is_active,
            max_seats=org.max_seats,
            billing_plan=org.billing_plan,
            billing_status=org.billing_status,
            billing_cycle=org.billing_cycle,
            created_at=org.created_at,
            seat_count=seat_ct or 0,
            active_sessions=active_sess or 0,
            scenario_count=scen_ct or 0,
        )
        for org, seat_ct, active_sess, scen_ct in result.all()
    ]


@router.post(
    "/organizations/",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    data: OrganizationCreate,
    user: RequireAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationRead:
    """Create a new organization.

    Requires *platform-admin* role.  Validates slug uniqueness before
    insert.
    """
    existing = await org_repo.get_by_slug(session, data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{data.slug}' already exists",
        )

    org = await org_repo.create(session, data)
    logger.info("Created organization: %s (%s)", org.id, org.slug)
    return OrganizationRead.model_validate(org)


@router.get("/organizations/{org_id}", response_model=OrganizationWithStats)
async def get_organization(
    org_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationWithStats:
    """Get organization details with live statistics.

    Org-admins can only view their own organization.  Platform-admins
    can view any organization.
    """
    verify_org_access(user, org_id)

    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    seat_count = await session.scalar(
        select(func.count(Seat.id)).where(Seat.organization_id == org_id, Seat.is_active.is_(True))
    )
    active_sessions = await session.scalar(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.org_id == org_id,
            TrainingSession.status == "active",
        )
    )
    scenario_count = await session.scalar(
        select(func.count(Scenario.id)).where(Scenario.org_id == org_id)
    )

    return OrganizationWithStats(
        id=org.id,
        name=org.name,
        slug=org.slug,
        logo_url=org.logo_url,
        is_active=org.is_active,
        max_seats=org.max_seats,
        billing_plan=org.billing_plan,
        billing_status=org.billing_status,
        billing_cycle=org.billing_cycle,
        created_at=org.created_at,
        seat_count=seat_count or 0,
        active_sessions=active_sessions or 0,
        scenario_count=scenario_count or 0,
    )


@router.put("/organizations/{org_id}", response_model=OrganizationRead)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationRead:
    """Update an organization.

    Org-admins can only update their own organization.  Platform-admins
    can update any organization.  Only the provided fields are changed.
    """
    verify_org_access(user, org_id)

    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(org, field, value)

    await session.flush()
    await session.refresh(org)
    logger.info("Updated organization: %s", org.id)
    return OrganizationRead.model_validate(org)


@router.delete("/organizations/{org_id}", status_code=status.HTTP_200_OK)
async def deactivate_organization(
    org_id: uuid.UUID,
    user: RequireAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Soft-delete (deactivate) an organization.

    Requires *platform-admin* role.  Sets ``is_active = False`` rather
    than physically deleting the record.
    """
    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    org.is_active = False
    await session.flush()
    logger.info("Deactivated organization: %s", org.id)
    return {"detail": f"Organization {org_id} deactivated"}


# ── Seat endpoints ─────────────────────────────────────────────────


@router.get("/organizations/{org_id}/seats", response_model=list[SeatWithUser])
async def list_seats(
    org_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> list[SeatWithUser]:
    """List all seats (members) in an organization.

    Org-admins can view seats only in their own organization.
    Platform-admins can view seats in any organization.
    """
    verify_org_access(user, org_id)

    result = await session.execute(
        select(Seat)
        .options(selectinload(Seat.user))
        .where(Seat.organization_id == org_id)
        .order_by(Seat.joined_at.desc())
    )
    return [
        SeatWithUser(
            id=seat.id,
            user_id=seat.user_id,
            organization_id=seat.organization_id,
            role=seat.role,
            is_active=seat.is_active,
            joined_at=seat.joined_at,
            user_email=seat.user.email,
            user_display_name=seat.user.display_name,
        )
        for seat in result.scalars().all()
    ]


@router.post(
    "/organizations/{org_id}/seats",
    response_model=SeatWithUser,
    status_code=status.HTTP_201_CREATED,
)
async def create_seat(
    org_id: uuid.UUID,
    data: SeatCreateRequest,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> SeatWithUser:
    """Add a user to an organization by email.

    Looks up the user by email address and creates a seat with the
    specified role.  Validates the organization's seat limit before
    inserting.
    """
    verify_org_access(user, org_id)

    # Verify organization exists
    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found",
        )

    # Look up target user by email
    target_user = await user_repo.get_by_email(session, data.email)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{data.email}' not found",
        )

    # Check for existing seat
    existing_seat = await seat_repo.get_user_org_seat(session, target_user.id, org_id)
    if existing_seat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a seat in this organization",
        )

    # Enforce seat limit
    current_count = await session.scalar(
        select(func.count(Seat.id)).where(Seat.organization_id == org_id, Seat.is_active.is_(True))
    )
    if (current_count or 0) >= org.max_seats:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization has reached its seat limit ({org.max_seats})",
        )

    seat = Seat(user_id=target_user.id, organization_id=org_id, role=data.role)
    session.add(seat)
    await session.flush()
    await session.refresh(seat)
    logger.info(
        "Created seat %s for user %s in org %s (role=%s)",
        seat.id,
        target_user.id,
        org_id,
        data.role,
    )

    return SeatWithUser(
        id=seat.id,
        user_id=seat.user_id,
        organization_id=seat.organization_id,
        role=seat.role,
        is_active=seat.is_active,
        joined_at=seat.joined_at,
        user_email=target_user.email,
        user_display_name=target_user.display_name,
    )


@router.put(
    "/organizations/{org_id}/seats/{seat_id}",
    response_model=SeatWithUser,
)
async def update_seat(
    org_id: uuid.UUID,
    seat_id: uuid.UUID,
    data: SeatRoleUpdate,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> SeatWithUser:
    """Update a seat's role within an organization.

    Org-admins can update seats only in their own organization.
    Platform-admins can update seats in any organization.
    """
    verify_org_access(user, org_id)

    result = await session.execute(
        select(Seat)
        .options(selectinload(Seat.user))
        .where(Seat.id == seat_id, Seat.organization_id == org_id)
    )
    seat = result.scalar_one_or_none()
    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat {seat_id} not found in organization {org_id}",
        )

    seat.role = data.role
    await session.flush()
    await session.refresh(seat)
    logger.info("Updated seat %s role to %s", seat.id, data.role)

    return SeatWithUser(
        id=seat.id,
        user_id=seat.user_id,
        organization_id=seat.organization_id,
        role=seat.role,
        is_active=seat.is_active,
        joined_at=seat.joined_at,
        user_email=seat.user.email,
        user_display_name=seat.user.display_name,
    )


@router.delete(
    "/organizations/{org_id}/seats/{seat_id}",
    status_code=status.HTTP_200_OK,
)
async def deactivate_seat(
    org_id: uuid.UUID,
    seat_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Deactivate (soft-delete) a seat in an organization.

    Sets ``is_active = False`` rather than physically deleting the seat.
    Org-admins can deactivate seats only in their own organization.
    """
    verify_org_access(user, org_id)

    result = await session.execute(
        select(Seat).where(Seat.id == seat_id, Seat.organization_id == org_id)
    )
    seat = result.scalar_one_or_none()
    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat {seat_id} not found in organization {org_id}",
        )

    seat.is_active = False
    await session.flush()
    logger.info("Deactivated seat %s in org %s", seat.id, org_id)
    return {"detail": f"Seat {seat_id} deactivated"}


# ── User endpoints ─────────────────────────────────────────────────


@router.get("/users/", response_model=list[UserRead])
async def list_users(
    user: RequireAdmin,
    search: str | None = Query(default=None, min_length=1, max_length=320),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserRead]:
    """List all users with optional email search.

    Requires *platform-admin* role.  Pass ``?search=`` to filter by
    email (case-insensitive partial match).
    """
    query = select(User).order_by(User.created_at.desc())

    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    result = await session.execute(query.limit(limit).offset(offset))
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.get("/users/{user_id}", response_model=UserWithSeats)
async def get_user(
    user_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> UserWithSeats:
    """Get user details with their organization memberships.

    Org-admins can only view users that have a seat in their
    organization.  Platform-admins can view any user.
    """
    result = await session.execute(
        select(User).options(selectinload(User.seats)).where(User.id == user_id)
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    await _verify_user_in_org(user, target, session)
    return UserWithSeats.model_validate(target)


@router.put("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> UserRead:
    """Update a user's display name or active status.

    Org-admins can only update users that have a seat in their
    organization.  Platform-admins can update any user.
    """
    target = await user_repo.get_by_id(session, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    await _verify_user_in_org(user, target, session)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(target, field, value)

    await session.flush()
    await session.refresh(target)
    logger.info("Admin updated user %s", user_id)
    return UserRead.model_validate(target)


# ── Platform statistics ────────────────────────────────────────────


@router.get("/stats", response_model=AdminStats)
async def get_platform_stats(
    user: RequireAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> AdminStats:
    """Platform-wide statistics for the admin dashboard.

    Requires *platform-admin* role.
    """
    total_orgs = await session.scalar(select(func.count(Organization.id))) or 0
    total_users = await session.scalar(select(func.count(User.id))) or 0
    total_sessions = await session.scalar(select(func.count(TrainingSession.id))) or 0
    total_scenarios = await session.scalar(select(func.count(Scenario.id))) or 0
    active_sessions = (
        await session.scalar(
            select(func.count(TrainingSession.id)).where(
                TrainingSession.status == "active",
            )
        )
        or 0
    )

    return AdminStats(
        total_orgs=total_orgs,
        total_users=total_users,
        total_sessions=total_sessions,
        total_scenarios=total_scenarios,
        active_sessions=active_sessions,
    )


# ── Private helpers ────────────────────────────────────────────────


async def _verify_user_in_org(
    requester: RequireOrgAdmin,
    target: User,
    session: AsyncSession,
) -> None:
    """Verify an org-admin can access the target user.

    Platform admins bypass this check.  Org-admins must share at least
    one active organization with the target user.

    Args:
        requester: The authenticated admin/org-admin from JWT.
        target: The user being accessed.
        session: Active database session.

    Raises:
        HTTPException: 403 if the requester cannot access the target user.
    """
    if is_platform_admin(requester):
        return

    org_id = get_user_org_id(requester)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization context",
        )

    seat = await seat_repo.get_user_org_seat(session, target.id, org_id)
    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of your organization",
        )


# ── Feature flags ──────────────────────────────────────────────────


@router.get(
    "/organizations/{org_id}/features",
    response_model=OrganizationFeaturesResponse,
)
async def get_organization_features(
    org_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationFeaturesResponse:
    """Get enabled features for an organization.

    Org-admins can only view their own organization's features.
    Platform-admins can view any organization.
    """
    verify_org_access(user, org_id)
    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationFeaturesResponse(
        org_id=org.id,
        enabled_features=org.enabled_features,
    )


@router.put(
    "/organizations/{org_id}/features",
    response_model=OrganizationFeaturesResponse,
)
async def update_organization_features(
    org_id: uuid.UUID,
    data: OrganizationFeaturesUpdate,
    _user: RequireAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationFeaturesResponse:
    """Enable or disable features for an organization (platform-admin only)."""
    org = await org_repo.get_by_id(session, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    valid = {"hangar", "squawk", "tower"}
    sanitized = [f for f in data.enabled_features if f in valid]
    if not sanitized:
        raise HTTPException(
            status_code=400,
            detail="At least one valid feature is required (hangar, squawk, tower)",
        )
    org.enabled_features = sanitized
    session.add(org)
    await session.flush()
    await session.refresh(org)
    logger.info("Updated features for org %s: %s", org.slug, sanitized)
    return OrganizationFeaturesResponse(
        org_id=org.id,
        enabled_features=org.enabled_features,
    )
