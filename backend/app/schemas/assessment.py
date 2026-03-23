"""Pydantic schemas for knowledge assessments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── KnowledgeAssessment ───────────────────────────────────────────


class AssessmentCreate(BaseModel):
    """Schema for creating a knowledge assessment."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    module_id: uuid.UUID | None = None
    questions: list[dict[str, Any]] = Field(default_factory=list)
    passing_score: float = Field(default=70.0, ge=0, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1)
    org_id: uuid.UUID | None = None
    is_published: bool = False


class AssessmentRead(BaseModel):
    """Schema returned when reading an assessment."""

    id: uuid.UUID
    title: str
    description: str | None = None
    module_id: uuid.UUID | None = None
    questions: list[dict[str, Any]]
    passing_score: float
    time_limit_minutes: int | None = None
    created_by: uuid.UUID | None = None
    org_id: uuid.UUID | None = None
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AssessmentResult ──────────────────────────────────────────────


class AssessmentSubmission(BaseModel):
    """Schema for submitting an assessment attempt."""

    answers: dict[str, Any] = Field(
        ...,
        description="Map of question_id → selected answer",
    )
    time_taken_seconds: int | None = Field(default=None, ge=0)


class AssessmentResultCreate(BaseModel):
    """Schema for creating an assessment result (server-side)."""

    assessment_id: uuid.UUID
    score: float = Field(..., ge=0, le=100)
    answers: dict[str, Any]
    passed: bool
    time_taken_seconds: int | None = Field(default=None, ge=0)


class AssessmentResultRead(BaseModel):
    """Schema returned when reading an assessment result."""

    id: uuid.UUID
    user_id: uuid.UUID
    assessment_id: uuid.UUID
    score: float
    answers: dict[str, Any]
    passed: bool
    time_taken_seconds: int | None = None
    completed_at: datetime

    model_config = {"from_attributes": True}
