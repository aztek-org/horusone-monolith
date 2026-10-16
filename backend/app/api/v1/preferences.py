"""User preferences API routes."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_preferences_repo import UserPreferencesRepository, _deep_merge
from app.db.session import get_db_session
from app.middleware.org_context import get_authenticated_user
from app.models.user import User
from app.schemas.user_preferences import (
    PreferencesData,
    SectionUpdate,
    UserPreferencesRead,
    UserPreferencesUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me/preferences", tags=["User Preferences"])
repo = UserPreferencesRepository()

_NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# Canonical section names that the PATCH endpoint accepts
_VALID_SECTIONS = frozenset({"keyboard_shortcuts", "voice", "display"})


def _default_preferences() -> dict[str, Any]:
    """Return the default preferences document.

    Returns:
        A dictionary matching the ``PreferencesData`` schema.
    """
    return PreferencesData().model_dump()


@router.get("/", response_model=UserPreferencesRead)
async def get_preferences(
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Return the current user's preferences.

    If no preferences row exists yet, a response with sensible defaults is
    returned (no row is persisted until the user explicitly updates).

    Args:
        local_user: The local ``User`` for the request (injected).
        session: Async database session (injected).

    Returns:
        The user's preferences document.
    """
    prefs = await repo.get_by_user_id(session, local_user.id)
    if prefs is None:
        return UserPreferencesRead(
            id=_NIL_UUID,
            user_id=local_user.id,
            preferences=_default_preferences(),
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )

    return UserPreferencesRead.model_validate(prefs)


@router.put("/", response_model=UserPreferencesRead)
async def update_preferences(
    body: UserPreferencesUpdate,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Update (deep-merge) the current user's preferences.

    The incoming ``preferences`` dict is deep-merged into the existing
    document.  Missing keys are preserved; provided keys overwrite.

    Args:
        body: The partial preferences payload.
        local_user: The local ``User`` for the request (injected).
        session: Async database session (injected).

    Returns:
        The full updated preferences document.
    """
    prefs = await repo.upsert(session, local_user.id, body.preferences)
    return UserPreferencesRead.model_validate(prefs)


@router.patch("/{section}", response_model=UserPreferencesRead)
async def update_preferences_section(
    section: str,
    body: SectionUpdate,
    local_user: User = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Update a single section of the user's preferences.

    Only the named *section* key is touched; the rest of the document is
    unchanged.  The section payload is deep-merged into the existing section
    data.

    Args:
        section: One of ``keyboard_shortcuts``, ``voice``, or ``display``.
        body: The section data to merge.
        local_user: The local ``User`` for the request (injected).
        session: Async database session (injected).

    Returns:
        The full updated preferences document.

    Raises:
        HTTPException: 400 if *section* is not a recognised section name.
    """
    if section not in _VALID_SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid section '{section}'. Valid sections: {', '.join(sorted(_VALID_SECTIONS))}"
            ),
        )

    # Fetch current prefs to merge at the section level
    existing = await repo.get_by_user_id(session, local_user.id)
    current_section = (existing.preferences or {}).get(section, {}) if existing else {}
    merged_section = _deep_merge(current_section, body.data) if current_section else body.data

    prefs = await repo.upsert(session, local_user.id, {section: merged_section})
    return UserPreferencesRead.model_validate(prefs)


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Returns:
        A timezone-aware ``datetime`` instance.
    """
    return datetime.now(timezone.utc)
