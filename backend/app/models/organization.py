"""Organization ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario
    from app.models.seat import Seat
    from app.models.training_module import TrainingModule


class Organization(Base):
    """Organization (tenant) for multi-tenancy.

    Every data-access query in the platform is scoped to an organization via
    its UUID primary key.  The ``slug`` field provides a human-readable,
    URL-safe identifier.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    billing_plan: Mapped[str] = mapped_column(String(32), nullable=False, default="starter")
    billing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="trial")
    billing_cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    enabled_features: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False,
        default=lambda: ["hangar", "squawk", "tower"],
        server_default="'[\"hangar\",\"squawk\",\"tower\"]'",
    )
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
    seats: Mapped[list[Seat]] = relationship(back_populates="organization")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="organization")
    training_modules: Mapped[list[TrainingModule]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug!r}>"
