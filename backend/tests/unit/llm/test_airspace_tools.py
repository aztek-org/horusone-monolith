"""Unit tests for the mock airspace lookup and route-intersection tools."""

from __future__ import annotations

import pytest

from app.services.llm.tools.airspace_tools import (
    AIRSPACE_DB,
    check_airspace,
    get_route_airspace,
)

KJFK_CENTER = AIRSPACE_DB["KJFK"]["center"]

# One latitude degree is ~60 NM, so a 0.16667° offset is ~10 NM from centre.
KJFK_10NM = (KJFK_CENTER[0] + 0.16667, KJFK_CENTER[1])
KJFK_18NM = (KJFK_CENTER[0] + 0.30, KJFK_CENTER[1])
KJFK_30NM = (KJFK_CENTER[0] + 0.50, KJFK_CENTER[1])


class TestCheckAirspace:
    def test_class_b_centre_at_low_altitude(self) -> None:
        info = check_airspace(KJFK_CENTER[0], KJFK_CENTER[1], altitude=3000)

        assert info["class"] == "B"
        assert info["airport"] == "KJFK"
        assert info["floor_ft"] == 0
        assert info["ceiling_ft"] == 7000
        assert info["distance_from_center_nm"] == pytest.approx(0.0)
        assert "ATC clearance required" in info["requirements"]
        assert info["frequencies"]["tower"] == "119.10"

    def test_second_ring_floor_applies_beyond_seven_nm(self) -> None:
        info = check_airspace(KJFK_10NM[0], KJFK_10NM[1], altitude=2000)

        assert info["class"] == "B"
        assert info["distance_from_center_nm"] == pytest.approx(10.0, abs=0.3)
        assert info["floor_ft"] == 1500

    def test_altitude_below_the_ring_floor_returns_class_e(self) -> None:
        info = check_airspace(KJFK_10NM[0], KJFK_10NM[1], altitude=1000)

        assert info["class"] == "E"
        assert info["airport"] is None

    def test_third_ring_floor_applies_beyond_twelve_nm(self) -> None:
        info = check_airspace(KJFK_18NM[0], KJFK_18NM[1], altitude=4000)

        assert info["class"] == "B"
        assert info["floor_ft"] == 3000

    def test_far_outside_every_ring_returns_class_e(self) -> None:
        info = check_airspace(KJFK_30NM[0], KJFK_30NM[1], altitude=3000)

        assert info["class"] == "E"
        assert info["airport"] is None
        assert info["requirements"] == []

    def test_above_the_class_b_ceiling_returns_class_e(self) -> None:
        info = check_airspace(KJFK_CENTER[0], KJFK_CENTER[1], altitude=9000)

        assert info["class"] == "E"


class TestGetRouteAirspace:
    def test_each_waypoint_is_annotated_with_its_name(self) -> None:
        route = [
            {"lat": KJFK_CENTER[0], "lng": KJFK_CENTER[1], "name": "KJFK", "altitude": 3000},
            {"lat": 0.0, "lng": 0.0, "name": "OVERSEA", "altitude": 5000},
        ]

        result = get_route_airspace(route)

        assert [entry["waypoint_name"] for entry in result] == ["KJFK", "OVERSEA"]
        assert result[0]["class"] == "B"
        assert result[1]["class"] == "E"

    def test_default_altitude_is_five_thousand_feet(self) -> None:
        result = get_route_airspace([{"lat": KJFK_CENTER[0], "lng": KJFK_CENTER[1]}])

        assert result[0]["class"] == "B"
        assert result[0]["waypoint_name"] == "UNKNOWN"

    def test_empty_route_returns_empty_list(self) -> None:
        assert get_route_airspace([]) == []
