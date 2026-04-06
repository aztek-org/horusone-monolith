"""Unit tests for scenario schema extensions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.scenario import ScenarioCreate


def test_scenario_create_accepts_custom_plan_template() -> None:
    """ScenarioCreate should accept optional scenario_type and plan template metadata."""
    payload = ScenarioCreate(
        name="RNAV Arrival Drill",
        description="Arrival procedure training",
        difficulty=3,
        airport_icao="KJFK",
        runway="31L",
        weather_preset="MVFR",
        phase="approach",
        scenario_type="training",
        flight_plan_template={
            "departure_icao": "KBOS",
            "arrival_icao": "KJFK",
            "route_string": "MERIT3 CAMRN Q818",
        },
    )
    assert payload.scenario_type == "training"
    assert payload.flight_plan_template is not None
    assert payload.flight_plan_template["arrival_icao"] == "KJFK"


def test_scenario_create_rejects_invalid_scenario_type() -> None:
    """ScenarioCreate should validate scenario_type against supported values."""
    with pytest.raises(ValidationError, match="scenario_type"):
        ScenarioCreate(
            name="Invalid Scenario Type",
            description=None,
            difficulty=1,
            airport_icao="KJFK",
            runway="04L",
            weather_preset="VFR",
            phase="ground",
            scenario_type="unsupported",
        )
