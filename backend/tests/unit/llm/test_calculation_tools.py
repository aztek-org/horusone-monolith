"""Unit tests for the pure-math aviation calculation tools.

These tools own all the numeric behaviour the validation agents build on, so
the assertions here pin real computed values (not just shapes).
"""

from __future__ import annotations

import pytest

from app.services.llm.tools.calculation_tools import (
    DEFAULT_TAS,
    FUEL_BURN_RATES,
    calculate_distance,
    calculate_ete,
    calculate_fuel_burn,
    calculate_fuel_reserve,
    calculate_groundspeed,
    calculate_heading,
    calculate_weight_balance,
)


class TestCalculateDistance:
    def test_one_degree_of_longitude_at_the_equator_is_about_60_nm(self) -> None:
        assert calculate_distance(0.0, 0.0, 0.0, 1.0) == pytest.approx(60.04, abs=0.05)

    def test_one_degree_of_latitude_is_about_60_nm(self) -> None:
        assert calculate_distance(0.0, 0.0, 1.0, 0.0) == pytest.approx(60.04, abs=0.05)

    def test_diagonal_degree_is_about_85_nm(self) -> None:
        assert calculate_distance(0.0, 0.0, 1.0, 1.0) == pytest.approx(84.9, abs=0.2)

    def test_distance_to_self_is_zero(self) -> None:
        assert calculate_distance(40.0, -73.0, 40.0, -73.0) == 0.0

    def test_distance_is_symmetric(self) -> None:
        there = calculate_distance(33.94, -118.40, 37.62, -122.38)
        back = calculate_distance(37.62, -122.38, 33.94, -118.40)
        assert there == pytest.approx(back, abs=1e-9)


class TestCalculateHeading:
    def test_due_north_is_zero(self) -> None:
        assert calculate_heading(0.0, 0.0, 1.0, 0.0) == pytest.approx(0.0, abs=1e-9)

    def test_due_east_is_ninety(self) -> None:
        assert calculate_heading(0.0, 0.0, 0.0, 1.0) == pytest.approx(90.0, abs=1e-9)

    def test_due_south_is_one_eighty(self) -> None:
        assert calculate_heading(0.0, 0.0, -1.0, 0.0) == pytest.approx(180.0, abs=1e-9)

    def test_due_west_is_two_seventy(self) -> None:
        assert calculate_heading(0.0, 0.0, 0.0, -1.0) == pytest.approx(270.0, abs=1e-9)

    def test_north_east_is_about_forty_five(self) -> None:
        assert calculate_heading(0.0, 0.0, 1.0, 1.0) == pytest.approx(45.0, abs=0.1)

    def test_result_is_always_in_zero_to_three_sixty(self) -> None:
        heading = calculate_heading(50.0, 8.0, 40.0, -74.0)
        assert 0.0 <= heading < 360.0


class TestCalculateGroundspeed:
    def test_headwind_subtracts_from_true_airspeed(self) -> None:
        assert calculate_groundspeed(100.0, 0.0, 20.0, 0.0) == pytest.approx(80.0)

    def test_tailwind_adds_to_true_airspeed(self) -> None:
        assert calculate_groundspeed(100.0, 180.0, 20.0, 0.0) == pytest.approx(120.0)

    def test_perpendicular_wind_leaves_tas_unchanged(self) -> None:
        assert calculate_groundspeed(100.0, 90.0, 20.0, 0.0) == pytest.approx(100.0)

    def test_groundspeed_never_goes_negative(self) -> None:
        assert calculate_groundspeed(10.0, 0.0, 50.0, 0.0) == 0.0


class TestCalculateEte:
    def test_one_hundred_twenty_nm_at_one_twenty_kts_is_sixty_minutes(self) -> None:
        assert calculate_ete(120.0, 120.0) == pytest.approx(60.0)

    def test_zero_groundspeed_returns_zero(self) -> None:
        assert calculate_ete(100.0, 0.0) == 0.0

    def test_zero_distance_returns_zero(self) -> None:
        assert calculate_ete(0.0, 100.0) == 0.0


class TestCalculateFuelBurn:
    def test_c172_one_hundred_nm_at_five_thousand_feet(self) -> None:
        # 8.5 gph × (1 − 0.02) = 8.33 gph; 100 NM / 110 kts = 0.909 h.
        assert calculate_fuel_burn(100.0, "C172", altitude=5000) == pytest.approx(
            7.57, abs=0.01
        )

    def test_sea_level_burn_is_higher_than_altitude_burn(self) -> None:
        sea_level = calculate_fuel_burn(100.0, "C172", altitude=0)
        high = calculate_fuel_burn(100.0, "C172", altitude=5000)
        assert sea_level == pytest.approx(7.73, abs=0.01)
        assert sea_level > high

    def test_headwind_increases_burn(self) -> None:
        calm = calculate_fuel_burn(100.0, "C172", altitude=5000)
        headwind = calculate_fuel_burn(100.0, "C172", altitude=5000, wind_component=20.0)
        assert headwind > calm

    def test_groundspeed_floor_of_thirty_knots(self) -> None:
        # 110 − 1000 would be negative, so the 30 kt floor applies.
        burn = calculate_fuel_burn(100.0, "C172", altitude=5000, wind_component=1000.0)
        assert burn == pytest.approx(27.77, abs=0.02)

    def test_tas_override_changes_time_enroute(self) -> None:
        burn = calculate_fuel_burn(100.0, "C172", altitude=5000, tas_override=220)
        assert burn == pytest.approx(3.79, abs=0.01)

    def test_unknown_aircraft_falls_back_to_default_rates(self) -> None:
        burn = calculate_fuel_burn(100.0, "ZZZZ", altitude=5000)
        # DEFAULT is 10 gph → 9.8 gph after altitude correction; TAS 120.
        assert burn == pytest.approx(9.8 * (100.0 / 120.0), abs=0.01)

    def test_altitude_correction_is_floored_at_eighty_percent(self) -> None:
        burn = calculate_fuel_burn(30.0, "C172", altitude=100000)
        # 8.5 × 0.8 = 6.8 gph → 6.8 × 30 / 110.
        assert burn == pytest.approx(6.8 * (30.0 / 110.0), abs=0.01)


class TestCalculateFuelReserve:
    def test_vfr_reserve_is_forty_five_minutes(self) -> None:
        assert calculate_fuel_reserve("VFR", 8.5) == pytest.approx(6.38, abs=0.01)

    def test_ifr_reserve_is_forty_five_minutes(self) -> None:
        assert calculate_fuel_reserve("IFR", 12.0) == pytest.approx(9.0)

    def test_flight_rules_is_case_insensitive(self) -> None:
        assert calculate_fuel_reserve("ifr", 12.0) == calculate_fuel_reserve("IFR", 12.0)

    def test_zero_burn_rate_needs_no_reserve(self) -> None:
        assert calculate_fuel_reserve("VFR", 0.0) == 0.0


class TestCalculateWeightBalance:
    def test_c172_empty_aircraft_is_within_limits(self) -> None:
        result = calculate_weight_balance("C172", fuel_weight=0.0, payload=0.0)

        assert result["total_weight"] == 1680.0
        assert result["max_gross"] == 2550
        assert result["cg_position"] == pytest.approx(41.15)
        assert result["within_weight"] is True
        assert result["within_cg"] is True
        assert result["within_limits"] is True

    def test_overweight_aircraft_fails_weight_check(self) -> None:
        result = calculate_weight_balance("C172", fuel_weight=0.0, payload=1000.0)

        assert result["total_weight"] == 2680.0
        assert result["within_weight"] is False
        assert result["within_limits"] is False

    def test_aft_cg_can_exceed_the_envelope(self) -> None:
        result = calculate_weight_balance(
            "C172", fuel_weight=0.0, payload=500.0, payload_arm=200.0
        )

        assert result["within_weight"] is True
        assert result["within_cg"] is False
        assert result["within_limits"] is False

    def test_unknown_aircraft_uses_default_envelope(self) -> None:
        result = calculate_weight_balance("C182", fuel_weight=0.0, payload=0.0)

        assert result["max_gross"] == 2600
        assert result["total_weight"] == 1700.0


def test_rate_tables_include_the_training_aircraft() -> None:
    assert FUEL_BURN_RATES["C172"] == 8.5
    assert FUEL_BURN_RATES["DEFAULT"] == 10.0
    assert DEFAULT_TAS["C172"] == 110
    assert DEFAULT_TAS["DEFAULT"] == 120
