"""Content management ORM models."""

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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ContentCategory(Base):
    """Hierarchical category for organising knowledge-base content.

    Categories form a tree via the nullable ``parent_id`` self-reference.
    The ``slug`` provides a URL-safe, unique identifier for routing.
    """

    __tablename__ = "content_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    parent: Mapped[ContentCategory | None] = relationship(
        remote_side="ContentCategory.id", backref="children"
    )
    articles: Mapped[list[ContentArticle]] = relationship(
        back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<ContentCategory slug={self.slug!r}>"


class ContentArticle(Base):
    """Knowledge-base article stored as Markdown.

    Articles belong to a category and can be scoped to an organisation
    (``org_id IS NULL`` means platform-wide).  Full-text search is
    supported via a GIN index on ``title`` and ``content``.
    """

    __tablename__ = "content_articles"
    __table_args__ = (
        Index(
            "idx_content_articles_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
        # NOTE: idx_content_articles_fts (GIN tsvector index on title+content)
        # is created via op.execute() in the Alembic migration because
        # Alembic autogenerate cannot diff to_tsvector expressions reliably.
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    difficulty_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    tags: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
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
    category: Mapped[ContentCategory] = relationship(
        back_populates="articles"
    )
    author: Mapped[User | None] = relationship()
    organization: Mapped[Organization | None] = relationship()

    def __repr__(self) -> str:
        return f"<ContentArticle slug={self.slug!r}>"
