"""Unit tests for organization schema billing fields."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def test_organization_create_defaults_billing_profile() -> None:
    """OrganizationCreate should apply sane default billing values."""
    payload = OrganizationCreate(name="Skybridge", slug="skybridge-aero", max_seats=120)
    assert payload.billing_plan == "starter"
    assert payload.billing_status == "trial"
    assert payload.billing_cycle == "monthly"


def test_organization_update_rejects_invalid_billing_status() -> None:
    """OrganizationUpdate should validate billing_status against supported values."""
    with pytest.raises(ValidationError, match="billing_status"):
        OrganizationUpdate(billing_status="unknown-status")
