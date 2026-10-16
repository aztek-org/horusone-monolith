"""Unit tests for FlightPlanRepository.

All database I/O is mocked via AsyncSession — no real DB connection needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.flight_plan_repository import FlightPlanRepository
from app.models.flight_plan import FlightPlan, FlightPlanLeg


# ── Mock helpers ───────────────────────────────────────────────────────


def _mock_session(scalar_result: object = None) -> AsyncMock:
    """Return an AsyncSession mock whose execute() returns a scalar proxy."""
    session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = scalar_result
    session.execute.return_value = result_proxy
    return session


def _mock_session_scalars(rows: list) -> AsyncMock:
    """Return an AsyncSession mock for queries using ``result.scalars().all()``."""
    session = AsyncMock()
    result_proxy = MagicMock()
    scalars_proxy = MagicMock()
    scalars_proxy.all.return_value = rows
    result_proxy.scalars.return_value = scalars_proxy
    session.execute.return_value = result_proxy
    return session


# ── FlightPlanRepository ───────────────────────────────────────────────


class TestFlightPlanRepository:
    """Tests for flight plan CRUD and leg queries."""

    @pytest.mark.asyncio
    async def test_create_flight_plan_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = FlightPlanRepository()
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()

        result = await repo.create_flight_plan(
            session,
            {"title": "Round robin", "departure_icao": "KJFK", "arrival_icao": "KBOS"},
            user_id,
            org_id,
        )

        assert isinstance(result, FlightPlan)
        assert result.departure_icao == "KJFK"
        assert result.arrival_icao == "KBOS"
        assert result.user_id == user_id
        assert result.org_id == org_id
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(result)

    @pytest.mark.asyncio
    async def test_get_flight_plan_found(self) -> None:
        fake = MagicMock()
        session = _mock_session(scalar_result=fake)
        repo = FlightPlanRepository()

        assert await repo.get_flight_plan(session, uuid.uuid4()) is fake

    @pytest.mark.asyncio
    async def test_get_flight_plan_not_found(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = FlightPlanRepository()

        assert await repo.get_flight_plan(session, uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_get_flight_plan_with_user_filter(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = FlightPlanRepository()

        await repo.get_flight_plan(session, uuid.uuid4(), user_id=uuid.uuid4())

        query = str(session.execute.await_args.args[0])
        assert "flight_plans.user_id" in query

    @pytest.mark.asyncio
    async def test_list_flight_plans_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = FlightPlanRepository()

        assert await repo.list_flight_plans(session, uuid.uuid4()) == rows

    @pytest.mark.asyncio
    async def test_list_flight_plans_applies_status_and_org_filters(self) -> None:
        session = _mock_session_scalars([])
        repo = FlightPlanRepository()

        await repo.list_flight_plans(
            session, uuid.uuid4(), org_id=uuid.uuid4(), status="draft"
        )

        query = str(session.execute.await_args.args[0])
        assert "flight_plans.org_id" in query
        assert "flight_plans.status" in query

    @pytest.mark.asyncio
    async def test_update_flight_plan_applies_fields(self) -> None:
        plan = MagicMock()
        session = _mock_session(scalar_result=plan)
        repo = FlightPlanRepository()

        result = await repo.update_flight_plan(
            session, uuid.uuid4(), {"title": "Updated"}, uuid.uuid4()
        )

        assert result is plan
        assert plan.title == "Updated"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_flight_plan_not_found_returns_none(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = FlightPlanRepository()

        assert (
            await repo.update_flight_plan(session, uuid.uuid4(), {"title": "x"}, uuid.uuid4())
            is None
        )
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_status_sets_new_status(self) -> None:
        plan = MagicMock()
        plan.status = "draft"
        session = _mock_session(scalar_result=plan)
        repo = FlightPlanRepository()

        result = await repo.update_status(session, uuid.uuid4(), "active", uuid.uuid4())

        assert result is plan
        assert plan.status == "active"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status_not_found_returns_none(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = FlightPlanRepository()

        assert await repo.update_status(session, uuid.uuid4(), "active", uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_delete_flight_plan_existing_returns_true(self) -> None:
        plan = MagicMock()
        session = _mock_session(scalar_result=plan)
        repo = FlightPlanRepository()

        assert await repo.delete_flight_plan(session, uuid.uuid4(), uuid.uuid4()) is True
        session.delete.assert_awaited_once_with(plan)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_flight_plan_missing_returns_false(self) -> None:
        session = _mock_session(scalar_result=None)
        repo = FlightPlanRepository()

        assert await repo.delete_flight_plan(session, uuid.uuid4(), uuid.uuid4()) is False
        session.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_add_leg_persists_and_returns(self) -> None:
        session = AsyncMock()
        session.add = MagicMock()
        repo = FlightPlanRepository()
        plan_id = uuid.uuid4()

        result = await repo.add_leg(session, plan_id, {"sequence": 1, "from_identifier": "KJFK"})

        assert isinstance(result, FlightPlanLeg)
        assert result.flight_plan_id == plan_id
        assert result.sequence == 1
        session.add.assert_called_once_with(result)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_legs_returns_rows(self) -> None:
        rows = [MagicMock(), MagicMock()]
        session = _mock_session_scalars(rows)
        repo = FlightPlanRepository()

        assert await repo.get_legs(session, uuid.uuid4()) == rows
