"""Unit tests for the flight-plan routes' Session-module calls."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import flight_plans
from app.db.session import get_db_session
from app.main import app
from app.middleware.auth import TokenUser, get_current_user
from app.middleware.org_context import (
    get_authenticated_user,
    get_org_id,
    require_active_seat,
)
from app.schemas.flight_plan import FlightPlanFromText


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
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A validation must retrieve the tenant's own manuals, not only global ones.

    ``TrainingSessionModule.validate`` resolves knowledge through
    ``HorusState.org_id``; with no ``org_id`` the retrieval predicate is
    ``org_id IS NULL``, so a tenant's private manuals are invisible to the one
    route that would use them.  The route already resolves the caller's
    organization for every other read and write, so validation must too.

    Driven through the HTTP app rather than by calling the handler directly, so
    the ``org_id`` this asserts is the one FastAPI actually bound to the caller:
    calling ``validate_flight_plan(org_id=...)`` as a keyword would stay green
    with ``Depends(get_org_id)`` deleted from the signature, which is the thing
    under test.
    """
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    session_module = _RecordingSessionModule()
    repo = _StubPlanRepo(_plan(plan_id))
    monkeypatch.setattr(flight_plans, "plan_repo", repo)
    client.app.state.session_module = session_module
    _override_route_dependencies(local_user_id=user_id, org_id=org_id)

    response = client.post(f"/api/v1/flight-plans/{plan_id}/validate")

    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True
    assert len(session_module.validated) == 1
    assert session_module.validated[0]["org_id"] == org_id
    assert session_module.validated[0]["user_id"] == user_id
    assert repo.statuses == [(str(plan_id), "validated", user_id)]


@pytest.mark.asyncio
async def test_validate_route_without_an_organization_stays_global_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A platform admin with no tenant still validates, fail-closed.

    ``org_id`` is optional on the route, so the tenant-less case must reach the
    module as ``None`` rather than raising or inventing a tenant.
    """
    plan_id = uuid.uuid4()
    session_module = _RecordingSessionModule()
    monkeypatch.setattr(flight_plans, "plan_repo", _StubPlanRepo(_plan(plan_id)))
    client.app.state.session_module = session_module
    _override_route_dependencies(local_user_id=uuid.uuid4(), org_id=None)

    response = client.post(f"/api/v1/flight-plans/{plan_id}/validate")

    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True
    assert session_module.validated[0]["org_id"] is None


def _override_route_dependencies(
    *, local_user_id: uuid.UUID, org_id: uuid.UUID | None
) -> None:
    """Bind the route's caller-facing dependencies, ``get_org_id`` included.

    ``get_org_id`` is overridden rather than left to run, so the tenant under test
    is named here and the assertion is about the route's wiring: with
    ``Depends(get_org_id)`` removed from the signature the override stops binding
    and the request fails instead of quietly validating globally.
    """
    token_user = TokenUser(
        keycloak_id="kc-pilot",
        email="pilot@test.com",
        display_name="Test Pilot",
        roles=["student"],
        organization_id=str(org_id) if org_id else None,
    )
    app.dependency_overrides[get_current_user] = lambda: token_user
    app.dependency_overrides[require_active_seat] = lambda: object()
    app.dependency_overrides[get_authenticated_user] = lambda: SimpleNamespace(
        id=local_user_id
    )
    app.dependency_overrides[get_org_id] = lambda: org_id
    app.dependency_overrides[get_db_session] = lambda: object()


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

    parser = flight_plans._get_parser(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(llm=object()))))

    assert isinstance(parser, _RecordingParser)
    assert len(_RecordingParser.calls) == 1
    args, kwargs = _RecordingParser.calls[0]
    assert kwargs == {}
    assert len(args) == 1
    assert args[0] is not None


# ── The parse routes must reuse the application's LLM, not build a new one ──


class _RecordingLLM:
    """A language-model stand-in that answers with one parseable JSON document."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[Any] = []

    async def generate(self, request: Any) -> Any:
        self.requests.append(request)
        return SimpleNamespace(
            text=self.text, provider="fake", model="fake", fallback_used=False
        )


class _CreatingPlanRepo:
    """Repository stand-in that records the ``data`` dict the route assembled."""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create_flight_plan(
        self, _db: object, data: dict[str, Any], user_id: Any, org_id: Any
    ) -> SimpleNamespace:
        self.created.append(data)
        return SimpleNamespace(id=uuid.uuid4(), **data)


_PARSE_JSON = '{"departure_icao": "KLAX", "arrival_icao": "KSFO", "aircraft_type": "C172"}'


def _no_second_client(built: list[object]) -> object:
    """Stand in for ``build_llm`` so any per-request construction is recorded."""

    def _build(_settings: object) -> object:
        built.append(_settings)
        return _RecordingLLM("{}")

    return _build


async def _call_from_text(
    request: object,
    *,
    repo: _CreatingPlanRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    monkeypatch.setattr(flight_plans, "plan_repo", repo)
    return await flight_plans.create_flight_plan_from_text(
        request=request,
        data=FlightPlanFromText(text="VFR from KLAX to KSFO at 5500 in a C172"),
        user=SimpleNamespace(roles=["student"], organization_id=None),
        _seat=object(),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        org_id=None,
        db=object(),
    )


async def _call_from_image(
    request: object,
    *,
    repo: _CreatingPlanRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    monkeypatch.setattr(flight_plans, "plan_repo", repo)
    return await flight_plans.create_flight_plan_from_image(
        request=request,
        file=SimpleNamespace(
            filename="plan.png",
            content_type="image/png",
            read=_read_bytes,
        ),
        user=SimpleNamespace(roles=["student"], organization_id=None),
        _seat=object(),
        local_user=SimpleNamespace(id=uuid.uuid4()),
        org_id=None,
        db=object(),
    )


async def _read_bytes() -> bytes:
    return b"not-really-a-png"


@pytest.mark.parametrize("call", [_call_from_text, _call_from_image])
async def test_parse_routes_reuse_the_applications_llm(
    call: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Building a parser must not build a second LLM client per request.

    ``FlightPlanParser()`` with no ``llm`` runs ``build_llm(get_settings())``,
    which constructs a fresh adapter per call; ``ChatGroq`` and ``ollama.Client``
    each own an httpx client that is never closed, so every ``/from-text`` and
    ``/from-image`` request leaked one.  The application already owns a single
    module on ``app.state.llm``; assert the route uses it, both by recording any
    call to ``build_llm`` and by proving the parse came from that module.
    """
    llm = _RecordingLLM(_PARSE_JSON)
    built: list[object] = []
    monkeypatch.setattr(
        "app.services.flight_plan_parser.build_llm", _no_second_client(built)
    )
    repo = _CreatingPlanRepo()

    await call(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(llm=llm))),
        repo=repo,
        monkeypatch=monkeypatch,
    )

    assert built == [], "the route built a second LLM client for one request"
    assert [request.purpose for request in llm.requests] == ["flight_plan_parse"]
    assert repo.created[0]["departure_icao"] == "KLAX"
    assert repo.created[0]["arrival_icao"] == "KSFO"
    assert repo.created[0]["aircraft_type"] == "C172"


@pytest.mark.parametrize("call", [_call_from_text, _call_from_image])
async def test_parser_construction_failure_still_yields_a_stub_plan(
    call: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A parser that cannot be built must degrade, not become a 500.

    Both route docstrings promise keyword-based extraction when the LLM is
    unavailable, and constructing the parser is the first step of that promise:
    a failure there is exactly as much "the LLM is unavailable" as a failure
    inside ``from_text``.  Here ``app.state`` carries no ``llm`` at all, so
    reading it raises — which proves the construction sits inside the fallback
    rather than above it.
    """
    repo = _CreatingPlanRepo()

    await call(
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),
        repo=repo,
        monkeypatch=monkeypatch,
    )

    assert len(repo.created) == 1
    assert repo.created[0]["departure_icao"] == "ZZZZ"
    assert repo.created[0]["arrival_icao"] == "ZZZZ"
    assert repo.created[0]["status"] == "draft"
