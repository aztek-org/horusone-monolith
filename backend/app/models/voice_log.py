"""VoiceLog ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.training_session import TrainingSession


class VoiceLog(Base):
    """Voice log entry model."""

    __tablename__ = "voice_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[TrainingSession] = relationship(back_populates="voice_logs")

    def __repr__(self) -> str:
        return f"<VoiceLog id={self.id} session={self.session_id} role={self.role!r}>"
