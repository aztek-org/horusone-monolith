"""Knowledge assessment ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.training_module import TrainingModule
    from app.models.user import User


class KnowledgeAssessment(Base):
    """Assessment definition containing questions and grading criteria.

    Assessments can be tied to a training module or stand alone.  The
    ``questions`` JSONB column holds an ordered list of question objects,
    each with a prompt, answer choices, and the correct answer key.
    """

    __tablename__ = "knowledge_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_modules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    questions: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    passing_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=70.0, server_default="70"
    )
    time_limit_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
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
    module: Mapped[TrainingModule | None] = relationship()
    creator: Mapped[User | None] = relationship()
    organization: Mapped[Organization | None] = relationship()
    results: Mapped[list[AssessmentResult]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeAssessment id={self.id} title={self.title!r}>"


class AssessmentResult(Base):
    """A user's attempt at completing a knowledge assessment.

    Stores the individual answers, computed score, and whether the
    attempt met the passing threshold.
    """

    __tablename__ = "assessment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    answers: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="{}"
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_taken_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()
    assessment: Mapped[KnowledgeAssessment] = relationship(
        back_populates="results"
    )

    def __repr__(self) -> str:
        return (
            f"<AssessmentResult id={self.id} "
            f"score={self.score} passed={self.passed}>"
        )
