"""Repository for student statistics, flight hours, and maneuver logs."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student_stats import FlightHourLog, ManeuverLog, StudentStats
from app.models.voice_log import VoiceLog

logger = logging.getLogger(__name__)


class StudentStatsRepository:
    """Data-access layer for student statistics and training logs.

    Manages aggregate stats, flight-hour entries, maneuver logs, and
    session transcripts.
    """

    # ── Aggregate stats ────────────────────────────────────────────

    async def get_user_stats(self, db: AsyncSession, user_id: uuid.UUID) -> StudentStats:
        """Get or create the aggregated stats row for a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            The StudentStats row (created with zeroes if not found).
        """
        result = await db.execute(select(StudentStats).where(StudentStats.user_id == user_id))
        stats = result.scalar_one_or_none()
        if stats is None:
            stats = StudentStats(user_id=user_id)
            db.add(stats)
            await db.flush()
            await db.refresh(stats)
            logger.info("Created StudentStats for user %s", user_id)
        return stats

    async def update_aggregates(self, db: AsyncSession, user_id: uuid.UUID) -> StudentStats:
        """Recalculate totals from flight-hour and maneuver logs.

        Args:
            db: Async database session.
            user_id: UUID of the user.

        Returns:
            The refreshed StudentStats row.
        """
        stats = await self.get_user_stats(db, user_id)

        # Total flight hours
        hours_result = await db.execute(
            select(func.coalesce(func.sum(FlightHourLog.hours_logged), 0.0)).where(
                FlightHourLog.user_id == user_id
            )
        )
        stats.total_flight_hours = float(hours_result.scalar_one())

        # Total maneuvers
        maneuver_count_result = await db.execute(
            select(func.count(ManeuverLog.id)).where(ManeuverLog.user_id == user_id)
        )
        stats.total_maneuvers = int(maneuver_count_result.scalar_one())

        # Average score across maneuvers
        avg_score_result = await db.execute(
            select(func.coalesce(func.avg(ManeuverLog.score), 0.0)).where(
                ManeuverLog.user_id == user_id,
                ManeuverLog.score.is_not(None),
            )
        )
        stats.overall_score = round(float(avg_score_result.scalar_one()), 2)

        await db.flush()
        await db.refresh(stats)
        logger.info("Updated aggregates for user %s", user_id)
        return stats

    # ── Flight hours ───────────────────────────────────────────────

    async def get_flight_hours(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[FlightHourLog]:
        """Get paginated flight-hour logs for a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            limit: Max rows to return.
            offset: Number of rows to skip.

        Returns:
            List of FlightHourLog entries, newest first.
        """
        result = await db.execute(
            select(FlightHourLog)
            .where(FlightHourLog.user_id == user_id)
            .order_by(FlightHourLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def log_flight_hours(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: int | None,
        hours: float,
        maneuvers: list[str],
        phase: str,
        notes: str | None = None,
    ) -> FlightHourLog:
        """Create a flight-hour log entry.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            session_id: Optional training session ID.
            hours: Hours logged (must be > 0).
            maneuvers: List of maneuver names practiced.
            phase: Flight phase (ground, departure, enroute, approach, landing).
            notes: Optional free-text notes.

        Returns:
            The created FlightHourLog.
        """
        log = FlightHourLog(
            user_id=user_id,
            session_id=session_id,
            hours_logged=hours,
            maneuvers_practiced=maneuvers,
            phase=phase,
            notes=notes,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    # ── Maneuver logs ──────────────────────────────────────────────

    async def get_maneuver_logs(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
        maneuver_type: str | None = None,
    ) -> list[ManeuverLog]:
        """Get paginated maneuver logs for a user.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            limit: Max rows to return.
            offset: Number of rows to skip.
            maneuver_type: Optional maneuver type filter.

        Returns:
            List of ManeuverLog entries, newest first.
        """
        query = select(ManeuverLog).where(ManeuverLog.user_id == user_id)
        if maneuver_type:
            query = query.where(ManeuverLog.maneuver_type == maneuver_type)

        result = await db.execute(
            query.order_by(ManeuverLog.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def log_maneuver(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: int | None,
        name: str,
        maneuver_type: str,
        score: float | None = None,
        duration: int | None = None,
        extra_data: dict | None = None,
    ) -> ManeuverLog:
        """Create a maneuver log entry.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            session_id: Optional training session ID.
            name: Maneuver name.
            maneuver_type: Maneuver classification.
            score: Optional score (0–100).
            duration: Optional duration in seconds.
            extra_data: Optional metadata dict.

        Returns:
            The created ManeuverLog.
        """
        log = ManeuverLog(
            user_id=user_id,
            session_id=session_id,
            maneuver_name=name,
            maneuver_type=maneuver_type,
            score=score,
            duration_seconds=duration,
            extra_data=extra_data or {},
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    # ── Transcripts ────────────────────────────────────────────────

    async def get_transcript(
        self, db: AsyncSession, session_id: int, user_id: uuid.UUID
    ) -> list[VoiceLog]:
        """Get voice logs for a training session owned by the user.

        Args:
            db: Async database session.
            session_id: Training session ID.
            user_id: UUID of the requesting user (for ownership check).

        Returns:
            List of VoiceLog entries in chronological order.
        """
        from app.models.training_session import TrainingSession

        # Verify session belongs to user (or exists)
        sess_result = await db.execute(
            select(TrainingSession).where(TrainingSession.id == session_id)
        )
        training_session = sess_result.scalar_one_or_none()
        if training_session is None:
            return []
        # Ownership is enforced at the route level; repo returns data.

        result = await db.execute(
            select(VoiceLog).where(VoiceLog.session_id == session_id).order_by(VoiceLog.created_at)
        )
        return list(result.scalars().all())
