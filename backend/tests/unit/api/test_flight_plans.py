"""Unit tests for the flight-plan routes' Session-module calls."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from app.api.v1 import flight_plans


class _RecordingSessionModule:
    """Session module stand-in that records the keyword arguments it is handed."""

    def __init__(self) -> None:
        self.validated: list[dict[str, Any]] = []

    async def validate(self, **kwargs: Any) -> SimpleNamespace:
        self.validated.append(kwargs)
        return SimpleNamespace(
            session_id=0,
            phase="ingestion",
            exchange_count=0,
            state={
                "validation_passed": True,
                "validation_results": [
                    {
                        "agent": "gatekeeper",
                        "passed": True,
                        "severity": "info",
                        "message": "Plan is structurally complete",
                    }
                ],
            },
        )


class _StubPlanRepo:
    """Flight-plan repository stand-in; the route only needs a plan and a status."""

    def __init__(self, plan: SimpleNamespace) -> None:
        self._plan = plan
        self.statuses: list[tuple[str, str, uuid.UUID]] = []

    async def get_flight_plan(
        self, _db: object, plan_id: uuid.UUID, user_id: uuid.UUID
    ) -> SimpleNamespace | None:
        return self._plan if self._plan.id == plan_id else None

    async def update_status(
        self, _db: object, plan_id: uuid.UUID, status: str, user_id: uuid.UUID
    ) -> None:
        self.statuses.append((str(plan_id), status, user_id))


def _plan(plan_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=plan_id,
        departure_icao="KLAX",
        arrival_icao="KSFO",
        alternate_icao=None,
        aircraft_type="C172",
        fuel_required_gal=40.0,
        fuel_reserve_gal=8.0,
        total_weight_lbs=2200.0,
        max_weight_lbs=2550.0,
    )


@pytest.mark.asyncio
async def test_validate_route_scopes_validation_to_the_callers_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validation must retrieve the tenant's own manuals, not only global ones.

    ``TrainingSessionModule.validate`` resolves knowledge through
    ``HorusState.org_id``; with no ``org_id`` the retrieval predicate is
    ``org_id IS NULL``, so a tenant's private manuals are invisible to the one
    route that would use them.  The route already resolves the caller's
    organization for every other read and write, so validation must too.
    """
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    session_module = _RecordingSessionModule()
    repo = _StubPlanRepo(_plan(plan_id))
    monkeypatch.setattr(flight_plans, "plan_repo", repo)

    response = await flight_plans.validate_flight_plan(
        plan_id=plan_id,
        request=SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(session_module=session_module))
        ),
        user=SimpleNamespace(roles=["student"], organization_id=str(org_id)),
        _seat=object(),
        org_id=org_id,
        local_user=SimpleNamespace(id=user_id),
        db=object(),
    )

    assert response.valid is True
    assert len(session_module.validated) == 1
    assert session_module.validated[0]["org_id"] == org_id
    assert session_module.validated[0]["user_id"] == user_id
    assert repo.statuses == [(str(plan_id), "validated", user_id)]


@pytest.mark.asyncio
async def test_validate_route_without_an_organization_stays_global_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A platform admin with no tenant still validates, fail-closed.

    ``org_id`` is optional on the route, so the tenant-less case must reach the
    module as ``None`` rather than raising or inventing a tenant.
    """
    plan_id = uuid.uuid4()
    session_module = _RecordingSessionModule()
    monkeypatch.setattr(flight_plans, "plan_repo", _StubPlanRepo(_plan(plan_id)))

    response = await flight_plans.validate_flight_plan(
        plan_id=plan_id,
        request=SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(session_module=session_module))
        ),
        user=SimpleNamespace(roles=["platform-admin"], organization_id=None),
        _seat=object(),
        org_id=None,
        local_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert response.valid is True
    assert session_module.validated[0]["org_id"] is None


class _RecordingParser:
    """Parser stand-in that records exactly what the call site passes it."""

    calls: ClassVar[list[tuple[tuple[object, ...], dict[str, Any]]]] = []

    def __init__(self, *args: object, **kwargs: Any) -> None:
        _RecordingParser.calls.append((args, kwargs))


def test_parser_construction_does_not_read_the_inert_ollama_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parser ignores both arguments, so the route must stop passing them.

    ``FlightPlanParser`` accepts ``ollama_base_url``/``model`` only to log that it
    ignores them (``app/services/flight_plan_parser.py``), and a debug log is not
    a use.  Reading the two flat settings here kept those compatibility aliases
    alive in ``app/`` after the last consumer had migrated, so assert on what
    the call site hands the constructor rather than on the parser's behaviour,
    which is unchanged either way.
    """
    _RecordingParser.calls.clear()
    monkeypatch.setattr(flight_plans, "FlightPlanParser", _RecordingParser)

    parser = flight_plans._get_parser()

    assert isinstance(parser, _RecordingParser)
    assert _RecordingParser.calls == [((), {})]
