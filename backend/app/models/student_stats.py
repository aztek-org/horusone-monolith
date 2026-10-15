"""Student statistics ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.training_session import TrainingSession
    from app.models.user import User


class StudentStats(Base):
    """Aggregated training statistics for a single user.

    Maintains running totals of flight hours, maneuvers, completed
    scenarios, and streak information.  Updated incrementally after
    each training session completes.
    """

    __tablename__ = "student_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    total_flight_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    total_maneuvers: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_scenarios_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_assessments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    overall_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    current_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    best_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"<StudentStats user_id={self.user_id} hours={self.total_flight_hours}>"


class FlightHourLog(Base):
    """Individual flight hour entry for a user.

    Records a discrete block of flight time, optionally linked to a
    training session.  The ``maneuvers_practiced`` JSONB column stores
    a list of maneuver names performed during the period.
    """

    __tablename__ = "flight_hour_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hours_logged: Mapped[float] = mapped_column(Float, nullable=False)
    maneuvers_practiced: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()
    session: Mapped[TrainingSession | None] = relationship()

    def __repr__(self) -> str:
        return f"<FlightHourLog id={self.id} user_id={self.user_id} hours={self.hours_logged}>"


class ManeuverLog(Base):
    """Individual maneuver practice record.

    Captures a single maneuver attempt with an optional score and
    duration.  The ``metadata`` JSONB column stores arbitrary
    context such as weather conditions or instructor comments.
    """

    __tablename__ = "maneuver_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    maneuver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    maneuver_type: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_data: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()
    session: Mapped[TrainingSession | None] = relationship()

    def __repr__(self) -> str:
        return f"<ManeuverLog id={self.id} maneuver={self.maneuver_name!r}>"
