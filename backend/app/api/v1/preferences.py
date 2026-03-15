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
from app.middleware.auth import CurrentUser
from app.schemas.user_preferences import (
    PreferencesData,
    SectionUpdate,
    UserPreferencesRead,
    UserPreferencesUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/me/preferences", tags=["User Preferences"])
repo = UserPreferencesRepository()

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
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Return the current user's preferences.

    If no preferences row exists yet, a response with sensible defaults is
    returned (no row is persisted until the user explicitly updates).

    Args:
        user: The authenticated user (injected).
        session: Async database session (injected).

    Returns:
        The user's preferences document.
    """
    _nil = uuid.UUID("00000000-0000-0000-0000-000000000000")

    user_uuid: uuid.UUID | None
    try:
        user_uuid = uuid.UUID(user.keycloak_id)
    except ValueError:
        user_uuid = None

    if user_uuid is None:
        # Dev/test mode — return defaults without DB lookup
        return UserPreferencesRead(
            id=_nil,
            user_id=_nil,
            preferences=_default_preferences(),
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )

    prefs = await repo.get_by_user_id(session, user_uuid)
    if prefs is None:
        return UserPreferencesRead(
            id=_nil,
            user_id=user_uuid,
            preferences=_default_preferences(),
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )

    return UserPreferencesRead.model_validate(prefs)


@router.put("/", response_model=UserPreferencesRead)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Update (deep-merge) the current user's preferences.

    The incoming ``preferences`` dict is deep-merged into the existing
    document.  Missing keys are preserved; provided keys overwrite.

    Args:
        body: The partial preferences payload.
        user: The authenticated user (injected).
        session: Async database session (injected).

    Returns:
        The full updated preferences document.
    """
    user_uuid = _resolve_user_uuid(user.keycloak_id)
    prefs = await repo.upsert(session, user_uuid, body.preferences)
    return UserPreferencesRead.model_validate(prefs)


@router.patch("/{section}", response_model=UserPreferencesRead)
async def update_preferences_section(
    section: str,
    body: SectionUpdate,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db_session),
) -> UserPreferencesRead:
    """Update a single section of the user's preferences.

    Only the named *section* key is touched; the rest of the document is
    unchanged.  The section payload is deep-merged into the existing section
    data.

    Args:
        section: One of ``keyboard_shortcuts``, ``voice``, or ``display``.
        body: The section data to merge.
        user: The authenticated user (injected).
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

    user_uuid = _resolve_user_uuid(user.keycloak_id)

    # Fetch current prefs to merge at the section level
    existing = await repo.get_by_user_id(session, user_uuid)
    current_section = (existing.preferences or {}).get(section, {}) if existing else {}
    merged_section = _deep_merge(current_section, body.data) if current_section else body.data

    prefs = await repo.upsert(session, user_uuid, {section: merged_section})
    return UserPreferencesRead.model_validate(prefs)


# ── Helpers ────────────────────────────────────────────────────────


def _resolve_user_uuid(keycloak_id: str) -> uuid.UUID:
    """Convert a keycloak_id string to a UUID.

    Args:
        keycloak_id: The user's Keycloak subject identifier.

    Returns:
        A UUID object.

    Raises:
        HTTPException: 400 if the keycloak_id is not a valid UUID.
    """
    try:
        return uuid.UUID(keycloak_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {keycloak_id}",
        ) from exc


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Returns:
        A timezone-aware ``datetime`` instance.
    """
    return datetime.now(timezone.utc)
