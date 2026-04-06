"""Scenario repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.scenario import Scenario
from app.schemas.scenario import ScenarioCreate


class ScenarioRepository(BaseRepository[Scenario, ScenarioCreate]):
    """Repository for Scenario CRUD operations."""

    def __init__(self) -> None:
        super().__init__(Scenario)

    async def get_by_airport(self, session: AsyncSession, airport_icao: str) -> list[Scenario]:
        """Get scenarios for a specific airport."""
        result = await session.execute(
            select(self.model).where(self.model.airport_icao == airport_icao)
        )
        return list(result.scalars().all())
