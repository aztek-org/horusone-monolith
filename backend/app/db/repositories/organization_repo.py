"""Organization repository."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate


class OrganizationRepository(BaseRepository[Organization, OrganizationCreate]):
    """Repository for Organization CRUD operations.

    Overrides the base ``get_by_id`` and ``delete`` methods to accept
    UUID primary keys instead of integer IDs.
    """

    def __init__(self) -> None:
        super().__init__(Organization)

    # ── UUID-aware overrides ───────────────────────────────────────

    async def get_by_id(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> Organization | None:
        """Get an organization by UUID primary key."""
        result = await session.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def delete(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> bool:
        """Delete an organization by UUID primary key."""
        obj = await self.get_by_id(session, record_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True

    # ── Custom queries ─────────────────────────────────────────────

    async def get_by_slug(
        self, session: AsyncSession, slug: str
    ) -> Organization | None:
        """Look up an organization by its URL-safe slug."""
        result = await session.execute(
            select(self.model).where(self.model.slug == slug)
        )
        return result.scalar_one_or_none()
