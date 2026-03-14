"""Seat repository."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.seat import Seat
from app.schemas.seat import SeatCreate


class SeatRepository(BaseRepository[Seat, SeatCreate]):
    """Repository for Seat CRUD operations.

    Overrides the base ``get_by_id`` and ``delete`` methods to accept
    UUID primary keys instead of integer IDs.
    """

    def __init__(self) -> None:
        super().__init__(Seat)

    # ── UUID-aware overrides ───────────────────────────────────────

    async def get_by_id(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> Seat | None:
        """Get a seat by UUID primary key."""
        result = await session.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def delete(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> bool:
        """Delete a seat by UUID primary key."""
        obj = await self.get_by_id(session, record_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True

    # ── Custom queries ─────────────────────────────────────────────

    async def get_user_seats(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[Seat]:
        """Get all seats (org memberships) for a user."""
        result = await session.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.joined_at.desc())
        )
        return list(result.scalars().all())

    async def get_org_seats(
        self, session: AsyncSession, org_id: uuid.UUID
    ) -> list[Seat]:
        """Get all seats (members) for an organization."""
        result = await session.execute(
            select(self.model)
            .where(self.model.organization_id == org_id)
            .order_by(self.model.joined_at.desc())
        )
        return list(result.scalars().all())

    async def get_user_org_seat(
        self, session: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> Seat | None:
        """Get a specific user's seat within an organization."""
        result = await session.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()
