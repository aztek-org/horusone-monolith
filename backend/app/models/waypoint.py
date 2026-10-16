"""Waypoint, scenario track, and flight insight ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario
    from app.models.training_session import TrainingSession


class Waypoint(Base):
    """Navigation waypoint, airport, or radio-navigation aid.

    Represents any named geographic point used in flight planning.  The
    ``type`` column distinguishes between waypoints, airports, VORs,
    NDBs, fixes, and intersections.
    """

    __tablename__ = "waypoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    scenario_waypoints: Mapped[list[ScenarioWaypoint]] = relationship(back_populates="waypoint")

    def __repr__(self) -> str:
        return f"<Waypoint id={self.id} name={self.name!r} type={self.type!r}>"


class ScenarioWaypoint(Base):
    """Ordered association between a scenario and its waypoints.

    The ``sequence_order`` column defines the route order.  Optional
    altitude and speed constraints encode approach/departure restrictions.
    """

    __tablename__ = "scenario_waypoints"

    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "sequence_order",
            name="uq_scenario_waypoint_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    waypoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waypoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    altitude_constraint: Mapped[str | None] = mapped_column(String(20), nullable=True)
    speed_constraint: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Relationships ──────────────────────────────────────────────
    scenario: Mapped[Scenario] = relationship(back_populates="waypoints")
    waypoint: Mapped[Waypoint] = relationship(back_populates="scenario_waypoints")

    def __repr__(self) -> str:
        return f"<ScenarioWaypoint scenario={self.scenario_id} seq={self.sequence_order}>"


class SessionTrack(Base):
    """Recorded flight track for session replay.

    Stores the complete trajectory as a JSONB array of track points,
    each containing lat, lng, altitude, heading, speed, and timestamp.
    """

    __tablename__ = "session_tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    track_points: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    total_distance_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    session: Mapped[TrainingSession] = relationship()

    def __repr__(self) -> str:
        return f"<SessionTrack session_id={self.session_id}>"


class FlightInsight(Base):
    """AI-generated insight for a training session.

    Insights flag deviations, performance highlights, communication
    issues, or procedural notes at a specific point in the session
    timeline.
    """

    __tablename__ = "flight_insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp_in_session: Mapped[float] = mapped_column(Float, nullable=False)
    extra_data: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──────────────────────────────────────────────
    session: Mapped[TrainingSession] = relationship()

    def __repr__(self) -> str:
        return f"<FlightInsight id={self.id} type={self.type!r} severity={self.severity!r}>"
