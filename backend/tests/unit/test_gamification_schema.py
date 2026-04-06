"""Unit tests for gamification schema write contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.gamification import BadgeCreate


def test_badge_create_accepts_valid_payload() -> None:
    """BadgeCreate should accept validated criteria and metadata."""
    payload = BadgeCreate(
        name="Arrival Pro",
        description="Complete 25 arrival scenarios",
        category="flight",
        tier="gold",
        criteria={"type": "scenarios", "threshold": 25},
    )
    assert payload.slug is None
    assert payload.sort_order == 0
    assert payload.criteria.type == "scenarios"
    assert payload.criteria.threshold == 25


def test_badge_create_rejects_invalid_category() -> None:
    """BadgeCreate should reject unsupported category values."""
    with pytest.raises(ValidationError, match="category"):
        BadgeCreate(
            name="Bad Category",
            description="Invalid category test",
            category="invalid",
            tier="bronze",
            criteria={"type": "score", "threshold": 80},
        )


def test_badge_create_rejects_invalid_criteria_type() -> None:
    """BadgeCreate should validate criteria.type against supported rules."""
    with pytest.raises(ValidationError, match="criteria.type"):
        BadgeCreate(
            name="Invalid Rule",
            description="Invalid criteria type test",
            category="custom",
            tier="custom",
            criteria={"type": "unknown", "threshold": 1},
        )
