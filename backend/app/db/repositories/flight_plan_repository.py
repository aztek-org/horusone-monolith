"""Repository for flight plans and flight plan legs."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.flight_plan import FlightPlan, FlightPlanLeg

logger = logging.getLogger(__name__)


class FlightPlanRepository:
    """Data-access layer for flight plans and their legs."""

    # ── Flight plan CRUD ───────────────────────────────────────────

    async def create_flight_plan(
        self,
        db: AsyncSession,
        data: dict,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None,
    ) -> FlightPlan:
        """Create a new flight plan.

        Args:
            db: Async database session.
            data: Dict of plan fields from the create schema.
            user_id: UUID of the owning user.
            org_id: Organisation scope (may be None).

        Returns:
            The created FlightPlan.
        """
        plan = FlightPlan(**data, user_id=user_id, org_id=org_id)
        db.add(plan)
        await db.flush()
        await db.refresh(plan)
        logger.info(
            "Created flight plan %s (%s→%s) for user %s",
            plan.id, plan.departure_icao, plan.arrival_icao, user_id,
        )
        return plan

    async def get_flight_plan(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> FlightPlan | None:
        """Get a single flight plan by ID, optionally restricted to a user.

        Args:
            db: Async database session.
            plan_id: UUID of the flight plan.
            user_id: If provided, only return the plan if it belongs to this user.

        Returns:
            The FlightPlan with legs eagerly loaded, or None.
        """
        query = (
            select(FlightPlan)
            .where(FlightPlan.id == plan_id)
            .options(selectinload(FlightPlan.legs))
        )
        if user_id is not None:
            query = query.where(FlightPlan.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_flight_plans(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[FlightPlan]:
        """List flight plans for a user, optionally filtered by org/status.

        Args:
            db: Async database session.
            user_id: UUID of the owning user.
            org_id: Optional organisation filter.
            status: Optional status filter.
            limit: Max rows to return.
            offset: Rows to skip.

        Returns:
            List of FlightPlan rows, newest first.
        """
        query = (
            select(FlightPlan)
            .where(FlightPlan.user_id == user_id)
            .options(selectinload(FlightPlan.legs))
        )
        if org_id is not None:
            query = query.where(FlightPlan.org_id == org_id)
        if status is not None:
            query = query.where(FlightPlan.status == status)

        result = await db.execute(
            query.order_by(FlightPlan.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_flight_plan(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        data: dict,
        user_id: uuid.UUID,
    ) -> FlightPlan | None:
        """Partially update a flight plan.

        Args:
            db: Async database session.
            plan_id: UUID of the flight plan.
            data: Dict of fields to update (only set keys).
            user_id: UUID of the owning user (ownership check).

        Returns:
            The updated FlightPlan, or None if not found / not owned.
        """
        plan = await self.get_flight_plan(db, plan_id, user_id)
        if plan is None:
            return None

        for field_name, value in data.items():
            setattr(plan, field_name, value)

        await db.flush()
        await db.refresh(plan)
        logger.info("Updated flight plan %s", plan.id)
        return plan

    async def update_status(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        new_status: str,
        user_id: uuid.UUID,
    ) -> FlightPlan | None:
        """Update the status of a flight plan.

        Args:
            db: Async database session.
            plan_id: UUID of the flight plan.
            new_status: New status value.
            user_id: UUID of the owning user.

        Returns:
            The updated FlightPlan, or None if not found.
        """
        plan = await self.get_flight_plan(db, plan_id, user_id)
        if plan is None:
            return None

        plan.status = new_status
        await db.flush()
        await db.refresh(plan)
        logger.info("Flight plan %s status → %s", plan.id, new_status)
        return plan

    async def delete_flight_plan(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        plan = await self.get_flight_plan(db, plan_id, user_id)
        if plan is None:
            return False
        await db.delete(plan)
        await db.flush()
        logger.info("Deleted flight plan %s", plan_id)
        return True

    # ── Legs ───────────────────────────────────────────────────────

    async def add_leg(
        self,
        db: AsyncSession,
        plan_id: uuid.UUID,
        leg_data: dict,
    ) -> FlightPlanLeg:
        """Add a leg to a flight plan.

        Args:
            db: Async database session.
            plan_id: UUID of the flight plan.
            leg_data: Dict of leg fields from the create schema.

        Returns:
            The created FlightPlanLeg.
        """
        leg = FlightPlanLeg(**leg_data, flight_plan_id=plan_id)
        db.add(leg)
        await db.flush()
        await db.refresh(leg)
        return leg

    async def get_legs(
        self, db: AsyncSession, plan_id: uuid.UUID
    ) -> list[FlightPlanLeg]:
        """Get all legs of a flight plan ordered by sequence.

        Args:
            db: Async database session.
            plan_id: UUID of the flight plan.

        Returns:
            List of FlightPlanLeg rows.
        """
        result = await db.execute(
            select(FlightPlanLeg)
            .where(FlightPlanLeg.flight_plan_id == plan_id)
            .order_by(FlightPlanLeg.sequence)
        )
        return list(result.scalars().all())
