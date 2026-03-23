"""Seat ORM model — join table between users and organizations."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Seat(Base):
    """Organization seat representing a user's membership and role.

    A seat ties a :class:`User` to an :class:`Organization` with a specific
    role (``admin``, ``instructor``, or ``student``).  The combination of
    ``user_id`` and ``organization_id`` is unique — a user can hold at most
    one seat per organization.
    """

    __tablename__ = "seats"

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_seat_user_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="student"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship(back_populates="seats")
    organization: Mapped[Organization] = relationship(back_populates="seats")

    def __repr__(self) -> str:
        return (
            f"<Seat id={self.id} user={self.user_id} "
            f"org={self.organization_id} role={self.role!r}>"
        )
