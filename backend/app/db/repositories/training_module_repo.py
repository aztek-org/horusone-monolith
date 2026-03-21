"""TrainingModule repository with UUID primary key and scenario management."""

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.base import BaseRepository
from app.models.training_module import TrainingModule, module_scenarios
from app.schemas.training_module import TrainingModuleCreate


class TrainingModuleRepository(BaseRepository[TrainingModule, TrainingModuleCreate]):
    """Repository for TrainingModule CRUD and scenario membership operations.

    Overrides the base ``get_by_id`` and ``delete`` methods to accept
    UUID primary keys instead of integer IDs.
    """

    def __init__(self) -> None:
        super().__init__(TrainingModule)

    # ── UUID-aware overrides ───────────────────────────────────────

    async def get_by_id(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> TrainingModule | None:
        """Get a training module by UUID primary key.

        Args:
            session: Active async database session.
            record_id: UUID of the training module.

        Returns:
            The TrainingModule if found, otherwise None.
        """
        result = await session.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()

    async def delete(  # type: ignore[override]
        self, session: AsyncSession, record_id: uuid.UUID
    ) -> bool:
        """Delete a training module by UUID primary key.

        Args:
            session: Active async database session.
            record_id: UUID of the training module to delete.

        Returns:
            True if the record was deleted, False if not found.
        """
        obj = await self.get_by_id(session, record_id)
        if obj is None:
            return False
        await session.delete(obj)
        return True

    # ── Org-scoped queries ─────────────────────────────────────────

    async def get_by_org(
        self,
        session: AsyncSession,
        org_id: uuid.UUID | None,
        *,
        include_global: bool = True,
    ) -> list[TrainingModule]:
        """Get training modules for an organisation, optionally including global ones.

        Args:
            session: Active async database session.
            org_id: UUID of the organisation.  Pass ``None`` to retrieve only
                global (platform-level) modules.
            include_global: When True, also return modules where
                ``org_id IS NULL`` (global / platform modules).

        Returns:
            List of matching TrainingModule rows ordered by sort_order.
        """
        stmt = select(self.model)

        if org_id is not None and include_global:
            stmt = stmt.where((self.model.org_id == org_id) | (self.model.org_id.is_(None)))
        elif org_id is not None:
            stmt = stmt.where(self.model.org_id == org_id)
        else:
            stmt = stmt.where(self.model.org_id.is_(None))

        stmt = stmt.order_by(self.model.sort_order, self.model.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── Eager-load with scenarios ──────────────────────────────────

    async def get_with_scenarios(
        self, session: AsyncSession, module_id: uuid.UUID
    ) -> TrainingModule | None:
        """Get a training module with its scenarios eagerly loaded.

        Args:
            session: Active async database session.
            module_id: UUID of the training module.

        Returns:
            The TrainingModule with ``scenarios`` populated, or None.
        """
        result = await session.execute(
            select(self.model)
            .where(self.model.id == module_id)
            .options(selectinload(self.model.scenarios))
        )
        return result.scalar_one_or_none()

    # ── Scenario membership management ─────────────────────────────

    async def add_scenario(
        self,
        session: AsyncSession,
        module_id: uuid.UUID,
        scenario_id: int,
        sort_order: int = 0,
    ) -> None:
        """Add a scenario to a module (idempotent via INSERT … ON CONFLICT).

        Args:
            session: Active async database session.
            module_id: UUID of the training module.
            scenario_id: Integer ID of the scenario to link.
            sort_order: Display order within the module.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(module_scenarios)
            .values(
                module_id=module_id,
                scenario_id=scenario_id,
                sort_order=sort_order,
            )
            .on_conflict_do_update(
                index_elements=["module_id", "scenario_id"],
                set_={"sort_order": sort_order},
            )
        )
        await session.execute(stmt)

    async def remove_scenario(
        self,
        session: AsyncSession,
        module_id: uuid.UUID,
        scenario_id: int,
    ) -> bool:
        """Remove a scenario from a module.

        Args:
            session: Active async database session.
            module_id: UUID of the training module.
            scenario_id: Integer ID of the scenario to unlink.

        Returns:
            True if a row was deleted, False if the association did not exist.
        """
        result = await session.execute(
            delete(module_scenarios).where(
                (module_scenarios.c.module_id == module_id)
                & (module_scenarios.c.scenario_id == scenario_id)
            )
        )
        return result.rowcount > 0  # type: ignore[union-attr]

    async def reorder_scenarios(
        self,
        session: AsyncSession,
        module_id: uuid.UUID,
        scenario_ids: list[int],
    ) -> None:
        """Bulk-update scenario ordering within a module.

        The position of each ``scenario_id`` in the list determines its new
        ``sort_order`` value (0-based).

        Args:
            session: Active async database session.
            module_id: UUID of the training module.
            scenario_ids: Ordered list of scenario IDs representing the
                desired display order.
        """
        for idx, scenario_id in enumerate(scenario_ids):
            await session.execute(
                update(module_scenarios)
                .where(
                    (module_scenarios.c.module_id == module_id)
                    & (module_scenarios.c.scenario_id == scenario_id)
                )
                .values(sort_order=idx)
            )
