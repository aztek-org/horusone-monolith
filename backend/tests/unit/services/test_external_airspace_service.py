"""Unit tests for the external AirspaceService boundary.

The service delegates to canned mock lookups; these tests pin both the
real lookup behaviour and the failure fallbacks without any network access.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.external import airspace_service as airspace_module
from app.services.external.airspace_service import AirspaceService


class TestCheckPoint:
    """Tests for AirspaceService.check_point()."""

    @pytest.mark.asyncio
    async def test_resolves_class_b_at_airport_center(self) -> None:
        service = AirspaceService()

        info = await service.check_point(40.6413, -73.7781, 1000)

        assert info["class"] == "B"
        assert info["airport"] == "KJFK"
        assert "ATC clearance required" in info["requirements"]
        assert info["frequencies"]["tower"] == "119.10"

    @pytest.mark.asyncio
    async def test_returns_class_e_outside_known_airspace(self) -> None:
        service = AirspaceService()

        info = await service.check_point(0.0, 0.0, 5000)

        assert info["class"] == "E"
        assert info["airport"] is None
        assert info["requirements"] == []

    @pytest.mark.asyncio
    async def test_forwards_coordinates_and_altitude_to_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _check(lat: float, lng: float, altitude: int) -> dict[str, Any]:
            captured.update(lat=lat, lng=lng, altitude=altitude)
            return {"class": "D"}

        monkeypatch.setattr(airspace_module, "check_airspace", _check)
        service = AirspaceService()

        result = await service.check_point(12.5, -45.25, 3500)

        assert result == {"class": "D"}
        assert captured == {"lat": 12.5, "lng": -45.25, "altitude": 3500}

    @pytest.mark.asyncio
    async def test_falls_back_to_default_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_lat: float, _lng: float, _alt: int) -> dict[str, Any]:
            raise RuntimeError("airspace lookup down")

        monkeypatch.setattr(airspace_module, "check_airspace", _boom)
        service = AirspaceService()

        info = await service.check_point(40.0, -73.0, 1000)

        assert info == AirspaceService._default_airspace()
        assert info["class"] == "E"
        assert info["floor_ft"] == 700
        assert info["ceiling_ft"] == 17999


class TestCheckRoute:
    """Tests for AirspaceService.check_route()."""

    @pytest.mark.asyncio
    async def test_returns_one_entry_per_waypoint(self) -> None:
        service = AirspaceService()
        waypoints = [
            {"lat": 40.6413, "lng": -73.7781, "altitude": 1000, "name": "JFK"},
            {"lat": 0.0, "lng": 0.0, "altitude": 5000, "name": "MID"},
        ]

        results = await service.check_route(waypoints)

        assert len(results) == 2
        assert results[0]["airport"] == "KJFK"
        assert results[1]["class"] == "E"

    @pytest.mark.asyncio
    async def test_forwards_waypoints_to_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[dict[str, Any]]] = []

        def _route(waypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
            captured.append(waypoints)
            return [{"class": "E"} for _ in waypoints]

        monkeypatch.setattr(airspace_module, "get_route_airspace", _route)
        service = AirspaceService()
        waypoints = [{"lat": 1.0, "lng": 2.0}]

        result = await service.check_route(waypoints)

        assert captured == [waypoints]
        assert result == [{"class": "E"}]

    @pytest.mark.asyncio
    async def test_falls_back_per_waypoint_on_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_waypoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
            raise RuntimeError("route lookup down")

        monkeypatch.setattr(airspace_module, "get_route_airspace", _boom)
        service = AirspaceService()
        waypoints = [{"lat": 1.0, "lng": 2.0}, {"lat": 3.0, "lng": 4.0}]

        results = await service.check_route(waypoints)

        assert results == [
            AirspaceService._default_airspace(),
            AirspaceService._default_airspace(),
        ]


class TestGetRequirements:
    """Tests for AirspaceService.get_requirements()."""

    @pytest.mark.asyncio
    async def test_returns_flat_requirements_list(self) -> None:
        service = AirspaceService()

        requirements = await service.get_requirements(40.6413, -73.7781, 1000)

        assert requirements == [
            "ATC clearance required",
            "Two-way radio",
            "Transponder with Mode C",
            "Student pilot operations require endorsement",
        ]

    @pytest.mark.asyncio
    async def test_handles_missing_requirements_key(self) -> None:
        service = AirspaceService()
        service.check_point = _async_return({"class": "E"})  # type: ignore[method-assign]

        assert await service.get_requirements(0.0, 0.0, 1000) == []


def _async_return(value: Any):
    """Build a coroutine function returning *value* for instance patching."""

    async def _inner(*_args: Any, **_kwargs: Any) -> Any:
        return value

    return _inner
