"""Unit tests for gamification route badge creation behavior."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import gamification
from app.middleware.auth import TokenUser
from app.schemas.gamification import BadgeCreate


def _build_user(roles: list[str], org_id: uuid.UUID | None = None) -> TokenUser:
    return TokenUser(
        keycloak_id="kc-user",
        email="user@test.com",
        display_name="User",
        roles=roles,
        organization_id=str(org_id) if org_id else None,
    )


def _build_badge_payload(name: str = "Arrival Pro") -> BadgeCreate:
    return BadgeCreate(
        name=name,
        description="Complete 25 arrival scenarios",
        category="flight",
        tier="gold",
        criteria={"type": "scenarios", "threshold": 25},
    )


@pytest.mark.asyncio
async def test_create_badge_requires_org_context_for_non_platform_admin() -> None:
    """Non-platform admins must have an org context for badge creation."""
    user = _build_user(["instructor"], org_id=None)
    db = AsyncMock()

    with pytest.raises(HTTPException, match="Organization context is required"):
        await gamification.create_badge(
            data=_build_badge_payload(),
            user=user,
            _seat=object(),
            org_id=None,
            db=db,
        )


@pytest.mark.asyncio
async def test_create_badge_conflicts_when_slug_exists_in_org_scope() -> None:
    """Badge creation should reject duplicate slugs in the same scope."""
    org_id = uuid.uuid4()
    user = _build_user(["org-admin"], org_id=org_id)
    db = AsyncMock()

    with (
        patch.object(
            gamification.gamification_repo,
            "get_badge_by_slug",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), slug="arrival-pro")),
        ) as get_by_slug,
        pytest.raises(HTTPException, match="already exists"),
    ):
        await gamification.create_badge(
            data=_build_badge_payload(),
            user=user,
            _seat=object(),
            org_id=org_id,
            db=db,
        )

    assert get_by_slug.await_args.args == (db, "arrival-pro", org_id)


@pytest.mark.asyncio
async def test_create_badge_passes_trimmed_payload_and_org_scope() -> None:
    """Badge creation should persist normalized payload under org scope."""
    org_id = uuid.uuid4()
    user = _build_user(["org-admin"], org_id=org_id)
    db = AsyncMock()

    with (
        patch.object(
            gamification.gamification_repo,
            "get_badge_by_slug",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            gamification.gamification_repo,
            "create_badge",
            new=AsyncMock(return_value=SimpleNamespace(slug="arrival-pro")),
        ) as create_badge,
    ):
        await gamification.create_badge(
            data=_build_badge_payload(name="  Arrival Pro  "),
            user=user,
            _seat=object(),
            org_id=org_id,
            db=db,
        )

    create_kwargs = create_badge.await_args.kwargs
    assert create_kwargs["org_id"] == org_id
    assert create_kwargs["payload"]["name"] == "Arrival Pro"
    assert create_kwargs["payload"]["description"] == "Complete 25 arrival scenarios"
    assert create_kwargs["payload"]["slug"] == "arrival-pro"
