"""TrainingModule ORM model and module_scenarios association table."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.scenario import Scenario
    from app.models.user import User

# ── Association table ─────────────────────────────────────────────
module_scenarios = Table(
    "module_scenarios",
    Base.metadata,
    Column(
        "module_id",
        UUID(as_uuid=True),
        ForeignKey("training_modules.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "scenario_id",
        Integer,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("sort_order", Integer, default=0, nullable=False, server_default="0"),
)


class TrainingModule(Base):
    """A curated collection of scenarios grouped into a training module.

    Modules can be organisation-scoped (``org_id`` set) or global / platform-
    level (``org_id IS NULL``).  Each module contains an ordered list of
    scenarios via the ``module_scenarios`` association table.
    """

    __tablename__ = "training_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Multi-tenancy / ownership ──────────────────────────────────
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # ── Module metadata ────────────────────────────────────────────
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Timestamps ─────────────────────────────────────────────────
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
    scenarios: Mapped[list[Scenario]] = relationship(
        secondary=module_scenarios, back_populates="modules"
    )
    organization: Mapped[Organization | None] = relationship(back_populates="training_modules")
    creator: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<TrainingModule id={self.id} name={self.name!r}>"
