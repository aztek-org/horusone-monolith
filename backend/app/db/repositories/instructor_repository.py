"""Repository for instructor profiles."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instructor import InstructorProfile
from app.models.seat import Seat

logger = logging.getLogger(__name__)


class InstructorRepository:
    """Data-access layer for instructor profile operations."""

    async def get_profile(self, db: AsyncSession, user_id: uuid.UUID) -> InstructorProfile | None:
        """Get an instructor profile by user ID.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            The InstructorProfile or None.
        """
        result = await db.execute(
            select(InstructorProfile).where(InstructorProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_profile(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: dict,
    ) -> InstructorProfile:
        """Create or update an instructor profile (upsert by user_id).

        Args:
            db: Async database session.
            user_id: UUID of the instructor user.
            data: Dict of profile fields to set.

        Returns:
            The created or updated InstructorProfile.
        """
        profile = await self.get_profile(db, user_id)
        if profile is None:
            profile = InstructorProfile(user_id=user_id, **data)
            db.add(profile)
            logger.info("Created instructor profile for user %s", user_id)
        else:
            for field_name, value in data.items():
                setattr(profile, field_name, value)
            logger.info("Updated instructor profile for user %s", user_id)

        await db.flush()
        await db.refresh(profile)
        return profile

    async def search_instructors(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None = None,
        specialization: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[InstructorProfile]:
        """Search instructor profiles with optional org and specialization filter.

        When ``org_id`` is provided, only instructors who hold an active
        instructor-role seat in that organisation are returned.

        Args:
            db: Async database session.
            org_id: Optional organisation filter.
            specialization: Optional specialization keyword to match.
            limit: Max results.
            offset: Rows to skip.

        Returns:
            List of InstructorProfile rows.
        """
        query = select(InstructorProfile)

        if org_id is not None:
            # Join with Seat to filter by org membership
            query = query.join(Seat, Seat.user_id == InstructorProfile.user_id).where(
                Seat.organization_id == org_id,
                Seat.is_active.is_(True),
                Seat.role.in_(["instructor", "admin"]),
            )

        if specialization:
            # JSONB array contains check — specializations is a JSON array
            query = query.where(InstructorProfile.specializations.op("@>")(f'["{specialization}"]'))

        result = await db.execute(
            query.order_by(InstructorProfile.rating.desc().nullslast()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
