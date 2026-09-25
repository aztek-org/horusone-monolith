"""PostgreSQL tests for training-session event retention (ADR-009).

``prune_old_events`` is the only guard on the 90-day deletion of
``TrainingSessionEvent`` provenance, so these tests pin the *window value*, not
merely "some old row went away": every event is planted either side of the
90-day boundary and both the surviving rows and the returned count are asserted.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.models.training_session import TrainingSession
from app.models.training_session_event import TrainingSessionEvent
from app.services.training_sessions.retention import prune_old_events

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="needs Postgres",
)

#: ADR-009's retention window. This is the rule under test, restated here
#: independently of ``retention.py`` so that the tests can disagree with it.
RETENTION_DAYS = 90

#: ``prune_old_events`` takes an ``int`` window, so the window is only ever a whole
#: number of days. Planting the straddling events half a day either side of the
#: boundary therefore pins the window to exactly ``RETENTION_DAYS``: at 89 days
#: the inside event becomes eligible, at 91 the outside one stops being eligible.
INSIDE = timedelta(days=RETENTION_DAYS, hours=-12)  # 89.5 days old
OUTSIDE = timedelta(days=RETENTION_DAYS, hours=12)  # 90.5 days old


@asynccontextmanager
async def _planted_session(ages: dict[str, timedelta]) -> AsyncIterator[int]:
    """Yield a fresh session id carrying one event per ``ages`` entry.

    Each event's ``event_type`` is the key and its ``created_at`` is
    ``now - age``; the key is what the assertions use to say which rows survived.
    """
    async with get_session_factory()() as db:
        training_session = TrainingSession(
            user_id=None,
            org_id=None,
            language="en",
            status="completed",
        )
        db.add(training_session)
        await db.flush()
        now = datetime.now(timezone.utc)
        db.add_all(
            TrainingSessionEvent(
                session_id=training_session.id,
                event_type=event_type,
                event_payload={},
                created_at=now - age,
            )
            for event_type, age in ages.items()
        )
        await db.commit()
        try:
            yield training_session.id
        finally:
            await db.execute(
                delete(TrainingSessionEvent).where(
                    TrainingSessionEvent.session_id == training_session.id
                )
            )
            await db.execute(
                delete(TrainingSession).where(TrainingSession.id == training_session.id)
            )
            await db.commit()


async def _survivors(db: AsyncSession, session_id: int) -> set[str]:
    return set(
        (
            await db.execute(
                select(TrainingSessionEvent.event_type).where(
                    TrainingSessionEvent.session_id == session_id
                )
            )
        )
        .scalars()
        .all()
    )


async def _stale_rows_tablewide(db: AsyncSession) -> int:
    """Count every event in the table that the rule says is past its window.

    ``prune_old_events`` is table-scoped by design, so the count it returns is
    table-scoped too. Deriving the expectation from the table keeps the count
    assertion exact no matter what unrelated events the rest of the suite has
    left behind, instead of hard-coding ``1`` and failing on someone else's row.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    return (
        await db.scalar(
            select(func.count())
            .select_from(TrainingSessionEvent)
            .where(TrainingSessionEvent.created_at < cutoff)
        )
        or 0
    )


@pytest.mark.asyncio
async def test_prune_removes_only_events_older_than_the_retention_window() -> None:
    """The straddling pair decides the window: 89.5 days stays, 90.5 days goes."""
    async with _planted_session(
        {"inside_window": INSIDE, "past_window": OUTSIDE}
    ) as session_id:
        async with get_session_factory()() as db:
            expected_removed = await _stale_rows_tablewide(db)
            assert expected_removed >= 1, "fixture must make at least one row eligible"

            removed = await prune_old_events(db, RETENTION_DAYS)
            await db.commit()

            assert removed == expected_removed
            assert await _survivors(db, session_id) == {"inside_window"}


@pytest.mark.asyncio
async def test_prune_returns_a_count_that_covers_every_eligible_row() -> None:
    """Three eligible rows go, one in-window row stays: the count must be 3."""
    ages = {
        "past_window_oldest": timedelta(days=400),
        "past_window_middle": timedelta(days=91),
        "past_window_nearest": OUTSIDE,
        "inside_window": INSIDE,
    }
    async with _planted_session(ages) as session_id:
        async with get_session_factory()() as db:
            expected_removed = await _stale_rows_tablewide(db)

            removed = await prune_old_events(db, RETENTION_DAYS)
            await db.commit()

            assert removed == expected_removed
            assert await _survivors(db, session_id) == {"inside_window"}


@pytest.mark.asyncio
async def test_prune_removes_nothing_when_every_event_is_inside_the_window() -> None:
    """A recent-only table is left untouched: zero rows, all three event types."""
    ages = {
        "just_created": timedelta(0),
        "one_day_old": timedelta(days=1),
        "nearest_inside": INSIDE,
    }
    async with _planted_session(ages) as session_id:
        async with get_session_factory()() as db:
            removed = await prune_old_events(db, RETENTION_DAYS)
            await db.commit()

            assert removed == 0
            assert await _survivors(db, session_id) == set(ages)
