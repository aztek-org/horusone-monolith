"""Unit tests for the knowledge-assessment schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentRead,
    AssessmentResultCreate,
    AssessmentResultRead,
    AssessmentSubmission,
)


class TestAssessmentCreate:
    def test_defaults(self) -> None:
        assessment = AssessmentCreate(title="Radio Ops")
        assert assessment.passing_score == 70.0
        assert assessment.questions == []
        assert assessment.time_limit_minutes is None
        assert assessment.is_published is False

    def test_title_required_and_non_empty(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            AssessmentCreate(title="")

    def test_passing_score_bounds(self) -> None:
        with pytest.raises(ValidationError, match="passing_score"):
            AssessmentCreate(title="T", passing_score=101)
        with pytest.raises(ValidationError, match="passing_score"):
            AssessmentCreate(title="T", passing_score=-1)

    def test_time_limit_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="time_limit_minutes"):
            AssessmentCreate(title="T", time_limit_minutes=0)


class TestAssessmentRead:
    def test_requires_server_fields(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentRead(title="T")


class TestAssessmentSubmission:
    def test_requires_answers(self) -> None:
        with pytest.raises(ValidationError, match="answers"):
            AssessmentSubmission()

    def test_accepts_answers_and_time(self) -> None:
        submission = AssessmentSubmission(answers={"q1": "a"}, time_taken_seconds=30)
        assert submission.answers == {"q1": "a"}

    def test_rejects_negative_time(self) -> None:
        with pytest.raises(ValidationError, match="time_taken_seconds"):
            AssessmentSubmission(answers={}, time_taken_seconds=-1)


class TestAssessmentResultCreate:
    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError, match="score"):
            AssessmentResultCreate(
                assessment_id=uuid.uuid4(), score=100.1, answers={}, passed=True
            )

    def test_valid_result(self) -> None:
        result = AssessmentResultCreate(
            assessment_id=uuid.uuid4(), score=85.0, answers={"q": "a"}, passed=True
        )
        assert result.time_taken_seconds is None


class TestAssessmentResultRead:
    def test_accepts_full_row(self) -> None:
        read = AssessmentResultRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            assessment_id=uuid.uuid4(),
            score=90.0,
            answers={},
            passed=True,
            completed_at="2024-01-01T00:00:00",
        )
        assert read.time_taken_seconds is None
