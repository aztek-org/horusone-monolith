"""Gamification ORM models — badges, user awards, and leaderboards."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Badge(Base):
    """Achievement badge that can be awarded to users.

    Badges are grouped by ``category`` (flight, communication, etc.)
    and tiered (bronze → platinum).  The ``criteria`` JSONB column
    stores machine-readable rules for automatic award evaluation.
    """

    __tablename__ = "badges"
    __table_args__ = (
        Index(
            "uq_badges_slug_shared",
            "slug",
            unique=True,
            postgresql_where=text("org_id IS NULL"),
        ),
        Index(
            "uq_badges_slug_org",
            "org_id",
            "slug",
            unique=True,
            postgresql_where=text("org_id IS NOT NULL"),
        ),
        Index(
            "uq_badges_name_shared",
            "name",
            unique=True,
            postgresql_where=text("org_id IS NULL"),
        ),
        Index(
            "uq_badges_name_org",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("org_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criteria: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="{}"
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    user_badges: Mapped[list[UserBadge]] = relationship(
        back_populates="badge"
    )
    organization: Mapped[Organization | None] = relationship()

    def __repr__(self) -> str:
        return f"<Badge slug={self.slug!r} tier={self.tier!r}>"


class UserBadge(Base):
    """Record of a badge awarded to a user.

    The unique constraint on ``(user_id, badge_id)`` prevents
    duplicate awards.
    """

    __tablename__ = "user_badges"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "badge_id", name="uq_user_badge"
        ),
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
    badge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    extra_data: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()
    badge: Mapped[Badge] = relationship(back_populates="user_badges")

    def __repr__(self) -> str:
        return (
            f"<UserBadge user_id={self.user_id} "
            f"badge_id={self.badge_id}>"
        )


class LeaderboardSnapshot(Base):
    """Point-in-time leaderboard snapshot.

    Generated periodically (daily, weekly, monthly, or all-time).
    The ``data`` JSONB column contains a ranked array of user entries
    with scores and metrics.
    """

    __tablename__ = "leaderboard_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    data: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    organization: Mapped[Organization | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"<LeaderboardSnapshot period={self.period!r} "
            f"org_id={self.org_id}>"
        )
