"""User repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.user import User
from app.schemas.user import UserCreate


class UserRepository(BaseRepository[User, UserCreate]):
    """Repository for User CRUD operations.

    Overrides the base ``get_by_id`` and ``delete`` methods to accept
    UUID primary keys instead of integer IDs.
    """

    def __init__(self) -> None:
        super().__init__(User)

    # ── UUID-aware overrides ───────────────────────────────────────

    async def get_by_id(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> User | None:
        """Get a user by UUID primary key."""
        result = await session.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def delete(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> bool:
        """Delete a user by UUID primary key."""
        obj = await self.get_by_id(session, record_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True

    # ── Custom queries ─────────────────────────────────────────────

    async def get_by_keycloak_id(self, session: AsyncSession, keycloak_id: str) -> User | None:
        """Look up a user by their Keycloak subject identifier."""
        result = await session.execute(
            select(self.model).where(self.model.keycloak_id == keycloak_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        """Look up a user by email address."""
        result = await session.execute(select(self.model).where(self.model.email == email))
        return result.scalar_one_or_none()
