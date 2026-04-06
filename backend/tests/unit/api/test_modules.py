"""Unit tests for training module route authorization and org scoping."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import modules
from app.middleware.auth import TokenUser
from app.schemas.training_module import ModuleScenarioAction, TrainingModuleCreate


def _build_user(roles: list[str], org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id=str(uuid.uuid4()),
        email="pilot@test.com",
        display_name="Pilot",
        roles=roles,
        organization_id=str(org_id) if org_id else None,
    )


@pytest.mark.asyncio
async def test_create_module_requires_org_context_for_non_platform_admin() -> None:
    """Non-platform module creation requires organization context."""
    user = _build_user(["instructor"], org_id=None)
    session = AsyncMock()

    with pytest.raises(HTTPException, match="Organization context is required"):
        await modules.create_module(
            data=TrainingModuleCreate(name="Arrival Plan"),
            user=user,
            session=session,
        )


@pytest.mark.asyncio
async def test_get_module_rejects_cross_org_access() -> None:
    """Non-admin users cannot fetch modules owned by another organization."""
    user_org = uuid.uuid4()
    other_org = uuid.uuid4()
    module_id = uuid.uuid4()
    user = _build_user(["org-admin"], org_id=user_org)
    session = AsyncMock()
    module = SimpleNamespace(id=module_id, org_id=other_org)

    with (
        patch.object(modules.repo, "get_with_scenarios", new=AsyncMock(return_value=module)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await modules.get_module(module_id=module_id, user=user, session=session)

    assert exc_info.value.status_code == 404


class _ScenarioLookupResult:
    """Simple SQL result stub for scenario id/org lookup."""

    def __init__(self, org_id: uuid.UUID | None) -> None:
        self._org_id = org_id

    def one_or_none(self) -> SimpleNamespace:
        return SimpleNamespace(id=99, org_id=self._org_id)


@pytest.mark.asyncio
async def test_add_scenario_rejects_scenarios_outside_module_org_scope() -> None:
    """Org-scoped modules can only include org-owned or shared scenarios."""
    user_org = uuid.uuid4()
    other_org = uuid.uuid4()
    module_id = uuid.uuid4()
    user = _build_user(["instructor"], org_id=user_org)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScenarioLookupResult(org_id=other_org))
    module = SimpleNamespace(id=module_id, org_id=user_org)

    with (
        patch.object(modules.repo, "get_by_id", new=AsyncMock(return_value=module)),
        patch.object(modules.repo, "add_scenario", new=AsyncMock()) as add_scenario,
        pytest.raises(HTTPException, match="outside this module organization scope"),
    ):
        await modules.add_scenario_to_module(
            module_id=module_id,
            data=ModuleScenarioAction(scenario_id=99, sort_order=0),
            user=user,
            session=session,
        )

    assert add_scenario.await_count == 0


@pytest.mark.asyncio
async def test_remove_scenario_rejects_shared_module_writes_for_non_platform_admin() -> None:
    """Only platform-admin can mutate shared modules."""
    module_id = uuid.uuid4()
    user = _build_user(["org-admin"], org_id=uuid.uuid4())
    session = AsyncMock()
    module = SimpleNamespace(id=module_id, org_id=None)

    with (
        patch.object(modules.repo, "get_by_id", new=AsyncMock(return_value=module)),
        patch.object(modules.repo, "remove_scenario", new=AsyncMock()) as remove_scenario,
        pytest.raises(HTTPException, match="Only platform-admin can modify shared modules"),
    ):
        await modules.remove_scenario_from_module(
            module_id=module_id,
            scenario_id=7,
            user=user,
            session=session,
        )

    assert remove_scenario.await_count == 0
