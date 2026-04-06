"""TrainingSession ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario
    from app.models.training_session_event import TrainingSessionEvent
    from app.models.user import User
    from app.models.voice_log import VoiceLog


class TrainingSession(Base):
    """Training session model."""

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # client_id kept for backward compatibility; nullable for new user-based sessions.
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenarios.id"), nullable=True
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Multi-tenancy / ownership ──────────────────────────────────
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    # ── Relationships ──────────────────────────────────────────────
    scenario: Mapped[Scenario | None] = relationship(back_populates="sessions")
    voice_logs: Mapped[list[VoiceLog]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[list[TrainingSessionEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    user: Mapped[User | None] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return (
            f"<TrainingSession id={self.id} client={self.client_id!r} "
            f"status={self.status!r}>"
        )
