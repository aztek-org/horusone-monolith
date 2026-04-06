"""Repository for waypoints, scenario waypoints, session tracks, and insights."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waypoint import FlightInsight, ScenarioWaypoint, SessionTrack, Waypoint

logger = logging.getLogger(__name__)


def _haversine_nm(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate great-circle distance in nautical miles.

    Args:
        lat1: Latitude of point 1 (degrees).
        lng1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lng2: Longitude of point 2 (degrees).

    Returns:
        Distance in nautical miles.
    """
    r_nm = 3440.065  # Earth radius in nautical miles
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_nm * c


class WaypointRepository:
    """Data-access layer for navigation waypoints and flight tracks."""

    # ── Waypoint search ────────────────────────────────────────────

    async def search_waypoints(
        self,
        db: AsyncSession,
        wp_type: str | None = None,
        near_lat: float | None = None,
        near_lng: float | None = None,
        radius_nm: float = 50.0,
        limit: int = 50,
    ) -> list[Waypoint]:
        """Search waypoints by type and/or proximity.

        When ``near_lat`` and ``near_lng`` are provided the results are
        filtered to those within ``radius_nm`` nautical miles using a
        bounding-box pre-filter followed by Haversine post-filter in
        Python (good enough for moderate result sets).

        Args:
            db: Async database session.
            wp_type: Optional waypoint type filter.
            near_lat: Latitude of search centre.
            near_lng: Longitude of search centre.
            radius_nm: Search radius in nautical miles.
            limit: Max results.

        Returns:
            List of matching Waypoint rows.
        """
        query = select(Waypoint)
        if wp_type:
            query = query.where(Waypoint.type == wp_type)

        if near_lat is not None and near_lng is not None:
            # Rough bounding box: 1 degree lat ≈ 60 NM
            deg_offset = radius_nm / 60.0
            query = query.where(
                Waypoint.lat.between(near_lat - deg_offset, near_lat + deg_offset),
                Waypoint.lng.between(near_lng - deg_offset, near_lng + deg_offset),
            )

        result = await db.execute(query.limit(limit * 2))  # over-fetch for post-filter
        waypoints = list(result.scalars().all())

        # Haversine post-filter when proximity search is active
        if near_lat is not None and near_lng is not None:
            waypoints = [
                wp
                for wp in waypoints
                if _haversine_nm(near_lat, near_lng, wp.lat, wp.lng) <= radius_nm
            ]

        return waypoints[:limit]

    async def get_waypoint(
        self, db: AsyncSession, waypoint_id: uuid.UUID
    ) -> Waypoint | None:
        """Get a single waypoint by ID.

        Args:
            db: Async database session.
            waypoint_id: UUID of the waypoint.

        Returns:
            The Waypoint or None.
        """
        result = await db.execute(
            select(Waypoint).where(Waypoint.id == waypoint_id)
        )
        return result.scalar_one_or_none()

    async def create_waypoint(
        self, db: AsyncSession, data: dict
    ) -> Waypoint:
        """Create a new waypoint.

        Args:
            db: Async database session.
            data: Dict of waypoint fields.

        Returns:
            The created Waypoint.
        """
        waypoint = Waypoint(**data)
        db.add(waypoint)
        await db.flush()
        await db.refresh(waypoint)
        logger.info("Created waypoint: %s (%s)", waypoint.id, waypoint.name)
        return waypoint

    # ── Scenario waypoints ─────────────────────────────────────────

    async def get_scenario_waypoints(
        self, db: AsyncSession, scenario_id: int
    ) -> list[ScenarioWaypoint]:
        """Get waypoints for a scenario ordered by sequence.

        Args:
            db: Async database session.
            scenario_id: Integer ID of the scenario.

        Returns:
            Ordered list of ScenarioWaypoint rows.
        """
        result = await db.execute(
            select(ScenarioWaypoint)
            .where(ScenarioWaypoint.scenario_id == scenario_id)
            .order_by(ScenarioWaypoint.sequence_order)
        )
        return list(result.scalars().all())

    async def add_scenario_waypoint(
        self,
        db: AsyncSession,
        scenario_id: int,
        waypoint_id: uuid.UUID,
        sequence: int,
        altitude_constraint: str | None = None,
        speed_constraint: str | None = None,
        notes: str | None = None,
    ) -> ScenarioWaypoint:
        """Link a waypoint to a scenario at a given sequence position.

        Args:
            db: Async database session.
            scenario_id: Integer ID of the scenario.
            waypoint_id: UUID of the waypoint.
            sequence: Sequence order in the route.
            altitude_constraint: Optional altitude constraint.
            speed_constraint: Optional speed constraint.
            notes: Optional notes.

        Returns:
            The created ScenarioWaypoint.
        """
        sw = ScenarioWaypoint(
            scenario_id=scenario_id,
            waypoint_id=waypoint_id,
            sequence_order=sequence,
            altitude_constraint=altitude_constraint,
            speed_constraint=speed_constraint,
            notes=notes,
        )
        db.add(sw)
        await db.flush()
        await db.refresh(sw)
        logger.info(
            "Added waypoint %s to scenario %d at seq %d",
            waypoint_id, scenario_id, sequence,
        )
        return sw

    # ── Session tracks ─────────────────────────────────────────────

    async def get_session_track(
        self, db: AsyncSession, session_id: int
    ) -> SessionTrack | None:
        """Get the flight track for a training session.

        Args:
            db: Async database session.
            session_id: Training session ID.

        Returns:
            The SessionTrack or None.
        """
        result = await db.execute(
            select(SessionTrack).where(SessionTrack.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def save_session_track(
        self,
        db: AsyncSession,
        session_id: int,
        track_points: list[dict[str, Any]],
        total_distance: float | None = None,
    ) -> SessionTrack:
        """Create or replace a session track.

        Args:
            db: Async database session.
            session_id: Training session ID.
            track_points: List of track-point dicts.
            total_distance: Total distance in NM.

        Returns:
            The SessionTrack.
        """
        result = await db.execute(
            select(SessionTrack).where(SessionTrack.session_id == session_id)
        )
        track = result.scalar_one_or_none()
        if track is not None:
            track.track_points = track_points
            track.total_distance_nm = total_distance
        else:
            track = SessionTrack(
                session_id=session_id,
                track_points=track_points,
                total_distance_nm=total_distance,
            )
            db.add(track)
        await db.flush()
        await db.refresh(track)
        return track

    # ── Flight insights ────────────────────────────────────────────

    async def get_flight_insights(
        self, db: AsyncSession, session_id: int
    ) -> list[FlightInsight]:
        """Get AI-generated insights for a session.

        Args:
            db: Async database session.
            session_id: Training session ID.

        Returns:
            List of FlightInsight rows.
        """
        result = await db.execute(
            select(FlightInsight)
            .where(FlightInsight.session_id == session_id)
            .order_by(FlightInsight.timestamp_in_session)
        )
        return list(result.scalars().all())

    async def create_flight_insight(
        self, db: AsyncSession, data: dict
    ) -> FlightInsight:
        """Create a flight insight record.

        Args:
            db: Async database session.
            data: Dict of insight fields.

        Returns:
            The created FlightInsight.
        """
        insight = FlightInsight(**data)
        db.add(insight)
        await db.flush()
        await db.refresh(insight)
        return insight
