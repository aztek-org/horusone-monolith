"""Airspace data service — async interface over mock airspace lookups.

In production, replace the internal mock calls with a real airspace
database or API such as `OpenAIP <https://www.openaip.net/>`_,
the FAA NASR subscription, or EuroControl's B2B services.

The public interface is fully async so swapping in ``httpx`` calls
requires no changes to callers.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.tools.airspace_tools import (
    check_airspace,
    get_route_airspace,
)

logger = logging.getLogger(__name__)


class AirspaceService:
    """Async interface for airspace classification data.

    Currently delegates to the synchronous mock helpers in
    ``app.services.llm.tools.airspace_tools``.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_point(
        self,
        lat: float,
        lng: float,
        altitude: int,
    ) -> dict[str, Any]:
        """Check the airspace class at a single geographic point.

        Args:
            lat: Latitude in decimal degrees.
            lng: Longitude in decimal degrees.
            altitude: Altitude MSL in feet.

        Returns:
            Dict with ``class``, ``airport``, ``distance_from_center_nm``,
            ``floor_ft``, ``ceiling_ft``, ``requirements``, ``frequencies``.
        """
        try:
            result = check_airspace(lat, lng, altitude)
            logger.debug(
                "Airspace check at (%.4f, %.4f, %dft): Class %s",
                lat,
                lng,
                altitude,
                result.get("class"),
            )
            return result
        except Exception:
            logger.exception("Failed airspace check at (%.4f, %.4f, %dft)", lat, lng, altitude)
            return self._default_airspace()

    async def check_route(
        self,
        waypoints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Check airspace along an entire route of waypoints.

        Each waypoint dict should contain ``lat``, ``lng``, and
        optionally ``altitude`` (feet MSL, default 5 000) and ``name``.

        Returns:
            List of airspace intersection dicts, one per waypoint.
        """
        try:
            results = get_route_airspace(waypoints)
            classes = [r.get("class", "?") for r in results]
            logger.debug(
                "Route airspace check (%d waypoints): %s",
                len(waypoints),
                " → ".join(classes),
            )
            return results
        except Exception:
            logger.exception("Failed route airspace check (%d waypoints)", len(waypoints))
            return [self._default_airspace() for _ in waypoints]

    async def get_requirements(
        self,
        lat: float,
        lng: float,
        altitude: int,
    ) -> list[str]:
        """Get a flat list of airspace requirements at a point.

        Convenience wrapper around ``check_point``.
        """
        info = await self.check_point(lat, lng, altitude)
        return list(info.get("requirements") or [])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_airspace() -> dict[str, Any]:
        """Return a safe fallback when the real lookup fails."""
        return {
            "class": "E",
            "airport": None,
            "distance_from_center_nm": None,
            "floor_ft": 700,
            "ceiling_ft": 17999,
            "requirements": [],
            "frequencies": {},
        }
