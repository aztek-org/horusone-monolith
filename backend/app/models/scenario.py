"""Scenario ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.training_module import TrainingModule
    from app.models.training_session import TrainingSession
    from app.models.user import User
    from app.models.waypoint import ScenarioWaypoint


class Scenario(Base):
    """Training scenario model."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    airport_icao: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    runway: Mapped[str] = mapped_column(String(10), nullable=False)
    weather_preset: Mapped[str] = mapped_column(String(10), nullable=False, default="VFR")
    phase: Mapped[str] = mapped_column(String(50), nullable=False, default="ground")
    scenario_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    flight_plan_template: Mapped[dict | None] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=True, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Multi-tenancy / ownership ──────────────────────────────────
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────────
    sessions: Mapped[list[TrainingSession]] = relationship(back_populates="scenario")
    organization: Mapped[Organization | None] = relationship(back_populates="scenarios")
    creator: Mapped[User | None] = relationship()
    modules: Mapped[list[TrainingModule]] = relationship(
        secondary="module_scenarios", back_populates="scenarios"
    )
    waypoints: Mapped[list[ScenarioWaypoint]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scenario id={self.id} name={self.name!r} airport={self.airport_icao!r}>"
