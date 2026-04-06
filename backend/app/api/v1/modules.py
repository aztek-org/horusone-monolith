"""Training module API routes."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.training_module_repo import TrainingModuleRepository
from app.db.session import get_db_session
from app.middleware.auth import (
    CurrentUser,
    RequireInstructor,
    RequireOrgAdmin,
    TokenUser,
)
from app.models.scenario import Scenario
from app.models.training_module import TrainingModule
from app.schemas.training_module import (
    ModuleScenarioAction,
    TrainingModuleCreate,
    TrainingModuleRead,
    TrainingModuleUpdate,
    TrainingModuleWithScenarios,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/modules", tags=["Training Modules"])
repo = TrainingModuleRepository()


# ── Helpers ────────────────────────────────────────────────────────


def _user_org_id(user: TokenUser) -> uuid.UUID | None:
    """Extract the organisation UUID from a TokenUser, or None for admins.

    Args:
        user: Authenticated user from JWT.

    Returns:
        The user's organisation UUID or None if the user has no org claim.
    """
    if user.organization_id:
        return uuid.UUID(user.organization_id)
    return None


def _is_platform_admin(user: TokenUser) -> bool:
    """Check whether the user holds the platform-admin role.

    Args:
        user: Authenticated user from JWT.

    Returns:
        True if the user is a platform admin.
    """
    return "platform-admin" in user.roles


def _require_user_org_id(user: TokenUser) -> uuid.UUID:
    """Get org_id for a non-platform user, or raise if unavailable."""
    org_id = _user_org_id(user)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context is required",
        )
    return org_id


def _assert_module_access(
    user: TokenUser,
    module: TrainingModule,
    *,
    write: bool,
) -> None:
    """Enforce org-scoped read/write access for a module."""
    if _is_platform_admin(user):
        return

    user_org_id = _require_user_org_id(user)

    if module.org_id is None:
        if write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform-admin can modify shared modules",
            )
        return

    if module.org_id != user_org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module.id} not found",
        )


# ── Routes ─────────────────────────────────────────────────────────


@router.get("/", response_model=list[TrainingModuleRead])
async def list_modules(
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[TrainingModuleRead]:
    """List training modules visible to the current user.

    Platform admins see all modules.  Other users see modules scoped to
    their organisation plus global (platform-level) modules.
    """
    if _is_platform_admin(user):
        return await repo.get_all(session, limit=limit, offset=offset)  # type: ignore[return-value]

    org_id = _user_org_id(user)
    return await repo.get_by_org(session, org_id, include_global=True)  # type: ignore[return-value]


@router.post(
    "/",
    response_model=TrainingModuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_module(
    data: TrainingModuleCreate,
    user: RequireInstructor,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingModuleRead:
    """Create a new training module.

    Only instructors, org-admins, and platform-admins may create modules.
    The ``created_by`` field is automatically set from the JWT.
    """
    # Non-platform-admins can only create within their own org
    if not _is_platform_admin(user):
        data.org_id = _require_user_org_id(user)

    module = repo.model(
        **data.model_dump(),
        created_by=uuid.UUID(user.keycloak_id) if user.keycloak_id else None,
    )
    session.add(module)
    await session.flush()
    await session.refresh(module)
    logger.info("Created training module: %s – %s", module.id, module.name)
    return module  # type: ignore[return-value]


@router.get("/{module_id}", response_model=TrainingModuleWithScenarios)
async def get_module(
    module_id: uuid.UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingModuleWithScenarios:
    """Get a training module by ID with its associated scenarios."""
    module = await repo.get_with_scenarios(session, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module_id} not found",
        )
    _assert_module_access(user, module, write=False)
    return module  # type: ignore[return-value]


@router.put("/{module_id}", response_model=TrainingModuleRead)
async def update_module(
    module_id: uuid.UUID,
    data: TrainingModuleUpdate,
    user: RequireInstructor,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingModuleRead:
    """Update an existing training module.

    Only fields present in the request body are updated (partial update).
    """
    module = await repo.get_by_id(session, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module_id} not found",
        )
    _assert_module_access(user, module, write=True)

    update_data = data.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(module, field_name, value)

    await session.flush()
    await session.refresh(module)
    logger.info("Updated training module: %s", module.id)
    return module  # type: ignore[return-value]


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module_id: uuid.UUID,
    user: RequireOrgAdmin,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a training module.

    Only org-admins and platform-admins may delete modules.
    """
    module = await repo.get_by_id(session, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module_id} not found",
        )
    _assert_module_access(user, module, write=True)
    await session.delete(module)
    logger.info("Deleted training module: %s", module_id)


# ── Scenario membership ───────────────────────────────────────────


@router.post(
    "/{module_id}/scenarios",
    status_code=status.HTTP_201_CREATED,
    response_model=TrainingModuleWithScenarios,
)
async def add_scenario_to_module(
    module_id: uuid.UUID,
    data: ModuleScenarioAction,
    user: RequireInstructor,
    session: AsyncSession = Depends(get_db_session),
) -> TrainingModuleWithScenarios:
    """Add a scenario to a training module (idempotent).

    If the scenario is already linked, its ``sort_order`` is updated.
    """
    module = await repo.get_by_id(session, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module_id} not found",
        )
    _assert_module_access(user, module, write=True)

    scenario_row = (
        await session.execute(
            select(Scenario.id, Scenario.org_id).where(Scenario.id == data.scenario_id)
        )
    ).one_or_none()
    if scenario_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {data.scenario_id} not found",
        )
    scenario_org_id = scenario_row.org_id
    if module.org_id is not None and scenario_org_id not in {None, module.org_id}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scenario is outside this module organization scope",
        )

    await repo.add_scenario(session, module_id, data.scenario_id, data.sort_order)
    await session.flush()

    # Return refreshed module with scenarios
    updated = await repo.get_with_scenarios(session, module_id)
    logger.info("Added scenario %d to module %s", data.scenario_id, module_id)
    return updated  # type: ignore[return-value]


@router.delete(
    "/{module_id}/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_scenario_from_module(
    module_id: uuid.UUID,
    scenario_id: int,
    user: RequireInstructor,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a scenario from a training module."""
    module = await repo.get_by_id(session, module_id)
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training module {module_id} not found",
        )
    _assert_module_access(user, module, write=True)

    removed = await repo.remove_scenario(session, module_id, scenario_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario {scenario_id} not in module {module_id}",
        )
    logger.info("Removed scenario %d from module %s", scenario_id, module_id)
