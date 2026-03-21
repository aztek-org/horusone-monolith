"""VoiceLog repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.voice_log import VoiceLog
from app.schemas.voice_log import VoiceLogCreate


class VoiceLogRepository(BaseRepository[VoiceLog, VoiceLogCreate]):
    """Repository for VoiceLog CRUD operations."""

    def __init__(self) -> None:
        super().__init__(VoiceLog)

    async def get_by_session(
        self, session: AsyncSession, training_session_id: int
    ) -> list[VoiceLog]:
        """Get all voice logs for a training session in chronological order."""
        result = await session.execute(
            select(self.model)
            .where(self.model.session_id == training_session_id)
            .order_by(self.model.created_at)
        )
        return list(result.scalars().all())
