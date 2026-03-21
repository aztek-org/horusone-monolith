"""TrainingSession repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.repositories.base import BaseRepository
from app.models.training_session import TrainingSession
from app.schemas.training_session import TrainingSessionCreate


class TrainingSessionRepository(BaseRepository[TrainingSession, TrainingSessionCreate]):
    """Repository for TrainingSession CRUD operations."""

    def __init__(self) -> None:
        super().__init__(TrainingSession)

    async def get_by_client_id(
        self, session: AsyncSession, client_id: str
    ) -> list[TrainingSession]:
        """Get all sessions for a client."""
        result = await session.execute(select(self.model).where(self.model.client_id == client_id))
        return list(result.scalars().all())

    async def get_with_logs(self, session: AsyncSession, session_id: int) -> TrainingSession | None:
        """Get a training session with all voice logs eagerly loaded."""
        result = await session.execute(
            select(self.model)
            .options(selectinload(self.model.voice_logs))
            .where(self.model.id == session_id)
        )
        return result.scalar_one_or_none()
