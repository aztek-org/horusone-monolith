"""Unit tests for instructor and scene schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.instructor import (
    InstructorProfileCreate,
    InstructorProfileRead,
    InstructorProfileUpdate,
    InstructorStatsRead,
    InstructorStudentRead,
    RecentSessionRead,
)
from app.schemas.scene import SceneRead


class TestInstructorProfileCreate:
    def test_defaults(self) -> None:
        profile = InstructorProfileCreate()
        assert profile.qualifications == []
        assert profile.certifications == []
        assert profile.specializations == []
        assert profile.availability == {}
        assert profile.bio is None


class TestInstructorProfileUpdate:
    def test_all_optional(self) -> None:
        update = InstructorProfileUpdate()
        assert update.qualifications is None
        assert update.bio is None


class TestInstructorProfileRead:
    def test_accepts_full_row(self) -> None:
        read = InstructorProfileRead(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            qualifications=["CFI"],
            certifications=[],
            specializations=[],
            availability={},
            total_students=4,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert read.rating is None
        assert read.total_students == 4


class TestInstructorStudentRead:
    def test_defaults(self) -> None:
        student = InstructorStudentRead(
            id="s1",
            user_id="u1",
            display_name="Ace",
            email="a@b.com",
            flight_hours=10.0,
            scenarios_completed=3,
            overall_score=85.0,
        )
        assert student.strengths == []
        assert student.weaknesses == []
        assert student.recent_sessions == []
        assert student.last_active is None


class TestInstructorStatsRead:
    def test_requires_counters(self) -> None:
        with pytest.raises(ValidationError):
            InstructorStatsRead(total_students=1)

    def test_accepts_full_stats(self) -> None:
        stats = InstructorStatsRead(
            total_students=5,
            active_sessions=2,
            average_student_score=80.0,
            assessments_created=3,
        )
        assert stats.assessments_created == 3


class TestRecentSessionRead:
    def test_defaults(self) -> None:
        session = RecentSessionRead(
            id="x",
            student_name="Ace",
            scenario_name="Pattern",
            score=90.0,
            status="completed",
            duration_minutes=20,
        )
        assert session.student_id is None
        assert session.started_at is None


class TestSceneRead:
    def test_accepts_scene_payload(self) -> None:
        scene = SceneRead(
            version="1.0.0",
            name="Pattern Work",
            aircraft={"type": "C172"},
            airports={"departure": "KJFK"},
            objectives=["hold short"],
            difficulty=2,
            knowledge_refs=["aim-4-3"],
        )
        assert scene.version == "1.0.0"
        assert scene.difficulty == 2

    def test_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            SceneRead(version="1.0.0", name="X")
