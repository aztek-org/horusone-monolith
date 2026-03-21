"""Scenario API routes with RBAC enforcement.

- ``GET  /`` — any authenticated user (org-scoped filtering)
- ``POST /`` — instructor or higher
- ``GET  /{scenario_id}`` — any authenticated user (org access verified)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import can_access_org, is_platform_admin
from app.db.session import get_db_session
from app.middleware.auth import CurrentUser, RequireInstructor
from app.middleware.org_context import get_authenticated_user, get_org_id
from app.models.scenario import Scenario
from app.models.user import User
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.get("/", response_model=list[ScenarioResponse])
async def list_scenarios(
    user: CurrentUser,
    org_id: UUID | None = Depends(get_org_id),
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> list[ScenarioResponse]:
    """List training scenarios visible to the current user.

    Platform admins see all scenarios.  Other users see scenarios that
    belong to their organization **plus** global (un-scoped) scenarios.
    Users without an organization see only global scenarios.
    """
    query = select(Scenario)

    if not is_platform_admin(user):
        if org_id:
            query = query.where((Scenario.org_id == org_id) | Scenario.org_id.is_(None))
        else:
            query = query.where(Scenario.org_id.is_(None))

    result = await session.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all())  # type: ignore[return-value]


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    data: ScenarioCreate,
    user: RequireInstructor,
    org_id: UUID | None = Depends(get_org_id),
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """Create a new training scenario.

    Requires the *instructor* role or higher.  The scenario is
    automatically scoped to the creator's organization.
    """
    scenario = Scenario(
        **data.model_dump(),
        org_id=org_id,
        created_by=local_user.id,
    )
    session.add(scenario)
    await session.flush()
    await session.refresh(scenario)
    logger.info("Created scenario: %s - %s (org=%s)", scenario.id, scenario.name, org_id)
    return scenario  # type: ignore[return-value]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """Get a specific training scenario by ID.

    Verifies the user has access to the scenario's organization.
    Global scenarios (``org_id IS NULL``) are accessible to all
    authenticated users.  Platform admins can access any scenario.
    """
    result = await session.execute(select(Scenario).where(Scenario.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not found",
        )

    # Global scenarios are accessible to everyone
    if scenario.org_id is not None and not can_access_org(user, scenario.org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this scenario",
        )

    return scenario  # type: ignore[return-value]
