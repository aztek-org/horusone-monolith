"""Unit tests for the TrainingModule schemas."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.training_module import (
    ModuleScenarioAction,
    TrainingModuleCreate,
    TrainingModuleRead,
    TrainingModuleUpdate,
    TrainingModuleWithScenarios,
)


class TestTrainingModuleCreate:
    def test_defaults(self) -> None:
        module = TrainingModuleCreate(name="VFR Basics")
        assert module.difficulty_level == 1
        assert module.estimated_duration_minutes is None
        assert module.org_id is None

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            TrainingModuleCreate(name="")

    def test_difficulty_bounds(self) -> None:
        with pytest.raises(ValidationError, match="difficulty_level"):
            TrainingModuleCreate(name="M", difficulty_level=6)

    def test_estimated_duration_positive(self) -> None:
        with pytest.raises(ValidationError, match="estimated_duration_minutes"):
            TrainingModuleCreate(name="M", estimated_duration_minutes=0)


class TestTrainingModuleUpdate:
    def test_all_optional(self) -> None:
        update = TrainingModuleUpdate()
        assert update.name is None
        assert update.is_published is None
        assert update.sort_order is None

    def test_rejects_negative_sort_order(self) -> None:
        with pytest.raises(ValidationError, match="sort_order"):
            TrainingModuleUpdate(sort_order=-1)


class TestModuleScenarioAction:
    def test_default_sort_order(self) -> None:
        action = ModuleScenarioAction(scenario_id=5)
        assert action.sort_order == 0

    def test_rejects_negative_sort_order(self) -> None:
        with pytest.raises(ValidationError, match="sort_order"):
            ModuleScenarioAction(scenario_id=5, sort_order=-1)


class TestTrainingModuleRead:
    def test_accepts_full_row(self) -> None:
        read = TrainingModuleRead(
            id=uuid.uuid4(),
            name="M",
            is_published=True,
            difficulty_level=2,
            sort_order=1,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert read.description is None
        assert read.created_by is None

    def test_with_scenarios_defaults_empty(self) -> None:
        module = TrainingModuleWithScenarios(
            id=uuid.uuid4(),
            name="M",
            is_published=False,
            difficulty_level=1,
            sort_order=0,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert module.scenarios == []
