"""User synchronization service — auto-creates users from Keycloak tokens."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_repo import UserRepository
from app.middleware.auth import TokenUser
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)

user_repo = UserRepository()


async def sync_user_from_token(session: AsyncSession, token_user: TokenUser) -> User:
    """Ensure a local User record exists for the authenticated Keycloak user.

    Creates the user on first login; updates display_name/email on subsequent
    logins if they changed in Keycloak.  If a user with the same email
    already exists (e.g. from seed data) its ``keycloak_id`` is adopted.

    Args:
        session: Active async database session.
        token_user: User info extracted from JWT token.

    Returns:
        The existing or newly-created User ORM instance.
    """
    existing = await user_repo.get_by_keycloak_id(session, token_user.keycloak_id)

    if existing:
        # Update fields that may have changed in Keycloak
        changed = False
        if token_user.email and existing.email != token_user.email:
            existing.email = token_user.email
            changed = True
        if token_user.display_name and existing.display_name != token_user.display_name:
            existing.display_name = token_user.display_name
            changed = True
        if changed:
            await session.flush()
            logger.info("Updated user %s from token", existing.id)
        return existing

    # Fallback: user may exist by email (e.g. created by seed or dev mode)
    if token_user.email:
        by_email = await user_repo.get_by_email(session, token_user.email)
        if by_email:
            by_email.keycloak_id = token_user.keycloak_id
            if token_user.display_name:
                by_email.display_name = token_user.display_name
            await session.flush()
            logger.info(
                "Linked existing user %s to keycloak_id %s",
                by_email.id,
                token_user.keycloak_id,
            )
            return by_email

    # Create new user — use sensible defaults for missing claims
    email = token_user.email or f"{token_user.keycloak_id}@placeholder.local"
    display_name = token_user.display_name or token_user.email or token_user.keycloak_id

    create_data = UserCreate(
        email=email,
        display_name=display_name,
        keycloak_id=token_user.keycloak_id,
    )
    new_user = await user_repo.create(session, create_data)
    logger.info("Created new user %s (keycloak=%s)", new_user.id, token_user.keycloak_id)
    return new_user
