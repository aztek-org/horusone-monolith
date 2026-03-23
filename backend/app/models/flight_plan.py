"""Flight plan ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.scenario import Scenario
    from app.models.user import User
    from app.models.waypoint import Waypoint


class FlightPlan(Base):
    """A structured flight plan with routing and weight/fuel data.

    Flight plans may originate from manual form entry, OCR of scanned
    documents, or free-text/image parsing.  The ``source_type`` column
    records the origin, and ``status`` tracks the plan lifecycle from
    draft through active use to completion.
    """

    __tablename__ = "flight_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    departure_icao: Mapped[str] = mapped_column(String(4), nullable=False)
    arrival_icao: Mapped[str] = mapped_column(String(4), nullable=False)
    alternate_icao: Mapped[str | None] = mapped_column(
        String(4), nullable=True
    )
    route_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    aircraft_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # ── Weight & fuel ──────────────────────────────────────────────
    fuel_required_gal: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    fuel_reserve_gal: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    total_weight_lbs: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    max_weight_lbs: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    cg_position: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Briefing data ──────────────────────────────────────────────
    weather_briefing: Mapped[dict] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="{}"
    )
    airspace_restrictions: Mapped[list] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=False, server_default="[]"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Metadata ───────────────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="form", server_default="form"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────
    user: Mapped[User] = relationship()
    scenario: Mapped[Scenario | None] = relationship()
    organization: Mapped[Organization | None] = relationship()
    legs: Mapped[list[FlightPlanLeg]] = relationship(
        back_populates="flight_plan", cascade="all, delete-orphan",
        order_by="FlightPlanLeg.sequence",
    )

    def __repr__(self) -> str:
        return (
            f"<FlightPlan id={self.id} "
            f"{self.departure_icao}→{self.arrival_icao}>"
        )


class FlightPlanLeg(Base):
    """A single leg within a flight plan route.

    Each leg connects two waypoints (or identifiers when no waypoint
    record exists) with distance, heading, altitude, and fuel data.
    """

    __tablename__ = "flight_plan_legs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    flight_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flight_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    from_waypoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waypoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_waypoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("waypoints.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_identifier: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    to_identifier: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )
    distance_nm: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnetic_heading: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    altitude: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_time_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    fuel_burn_gal: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    wind: Mapped[dict | None] = mapped_column(  # type: ignore[type-arg]
        JSONB, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Relationships ──────────────────────────────────────────────
    flight_plan: Mapped[FlightPlan] = relationship(back_populates="legs")
    from_waypoint: Mapped[Waypoint | None] = relationship(
        foreign_keys=[from_waypoint_id]
    )
    to_waypoint: Mapped[Waypoint | None] = relationship(
        foreign_keys=[to_waypoint_id]
    )

    def __repr__(self) -> str:
        return (
            f"<FlightPlanLeg id={self.id} seq={self.sequence} "
            f"{self.from_identifier}→{self.to_identifier}>"
        )
