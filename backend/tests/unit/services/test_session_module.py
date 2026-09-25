"""Behavioral tests for the persisted training Session module."""

import uuid

import pytest

from app.llm.adapters.fake_adapter import FakeAdapter
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneRegistry
from app.services.training_sessions.session_module import (
    MissingOrgError,
    SessionPendingInstructorError,
    TrainingSessionModule,
)
from app.services.training_sessions.session_store import InMemorySessionStore
from app.services.training_sessions.trace import InMemoryTraceRecorder
from app.services.training_sessions.types import (
    EndSessionCommand,
    SendTransmissionCommand,
    StartSessionCommand,
)


class _NoDb:
    """Async-session stand-in that records the module-owned commits."""

    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> "_NoDb":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _module(
    *,
    store: InMemorySessionStore | None = None,
    trace: InMemoryTraceRecorder | None = None,
    **kwargs: object,
) -> TrainingSessionModule:
    return TrainingSessionModule(
        store or InMemorySessionStore(),
        trace or InMemoryTraceRecorder(),
        SceneRegistry({DEFAULT_SCENE.version: DEFAULT_SCENE}),
        FakeAdapter(),
        db_session_factory=_NoDb,
        require_org=True,
        **kwargs,
    )


async def _start(
    module: TrainingSessionModule,
    org_id: uuid.UUID,
    session_id: int = 1,
) -> None:
    await module.start(
        StartSessionCommand(
            org_id,
            uuid.uuid4(),
            session_id,
            DEFAULT_SCENE.version,
            "en",
            {
                "departure_icao": "KLAX",
                "arrival_icao": "KSFO",
                "flight_rules": "VFR",
                "aircraft_type": "C172",
                "fuel_on_board": 30.0,
                "fuel_reserve": 5.0,
                "total_weight": 2000.0,
                "max_weight": 2450.0,
                "cruise_altitude": 3500,
                "route": [
                    {"name": "KLAX", "lat": 33.94, "lng": -118.40},
                    {"name": "KSFO", "lat": 37.62, "lng": -122.38},
                ],
            },
        )
    )


@pytest.mark.asyncio
async def test_send_then_send_preserves_exchange_count() -> None:
    module = _module()
    org_id = uuid.uuid4()
    await _start(module, org_id)

    first = await module.send(SendTransmissionCommand(org_id, 1, "Tower, request taxi"))
    second = await module.send(
        SendTransmissionCommand(org_id, 1, "Tower, ready for departure")
    )

    assert (first.exchange_count, second.exchange_count) == (1, 2)
    assert second.provider == "fake"


@pytest.mark.asyncio
async def test_missing_org_rejected() -> None:
    module = _module()

    with pytest.raises(MissingOrgError):
        await module.start(
            StartSessionCommand(None, uuid.uuid4(), 1, DEFAULT_SCENE.version, "en", {})
        )


@pytest.mark.asyncio
async def test_second_send_while_pending_instructor_raises() -> None:
    module = _module(interrupt_before_response=True)
    org_id = uuid.uuid4()
    await _start(module, org_id)

    interrupted = await module.send(
        SendTransmissionCommand(org_id, 1, "request clearance")
    )

    assert interrupted.pending_instructor is True
    assert interrupted.atc_response == ""
    with pytest.raises(SessionPendingInstructorError):
        await module.send(SendTransmissionCommand(org_id, 1, "again"))
    released = await module.await_instructor(org_id, 1)
    assert released is not None
    assert released.pending_instructor is False


@pytest.mark.asyncio
async def test_send_merges_context_overrides() -> None:
    module = _module()
    org_id = uuid.uuid4()
    await _start(module, org_id)

    await module.send(
        SendTransmissionCommand(org_id, 1, "Request climb", {"altitude": "3500"})
    )
    await module.send(
        SendTransmissionCommand(org_id, 1, "Position report", {"position": "10 NM"})
    )
    snapshot = await module.snapshot(org_id, 1)

    assert snapshot.state["context"] == {
        "altitude": "3500",
        "position": "10 NM",
    }


@pytest.mark.asyncio
async def test_new_module_instance_resumes_stored_exchange_count() -> None:
    store = InMemorySessionStore()
    org_id = uuid.uuid4()
    first_module = _module(store=store)
    await _start(first_module, org_id)
    await first_module.send(SendTransmissionCommand(org_id, 1, "First call"))

    resumed_module = _module(store=store)
    result = await resumed_module.send(SendTransmissionCommand(org_id, 1, "Second call"))

    assert result.exchange_count == 2
    snapshot = await resumed_module.snapshot(org_id, 1)
    assert snapshot.phase == "active"
    assert snapshot.exchange_count == 2


@pytest.mark.asyncio
async def test_end_scores_session_and_emits_completion_provenance() -> None:
    trace = InMemoryTraceRecorder()
    module = _module(trace=trace)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await module.start(
        StartSessionCommand(
            org_id,
            user_id,
            1,
            DEFAULT_SCENE.version,
            "en",
            {"departure_icao": "KLAX", "arrival_icao": "KSFO"},
        )
    )
    await module.send(SendTransmissionCommand(org_id, 1, "Tower, request taxi"))

    debrief = await module.end(EndSessionCommand(org_id, 1, {"total_sessions": 1}))
    snapshot = await module.snapshot(org_id, 1)
    session_id, event_type, payload = trace.events[-1]

    assert debrief.scoring["overall_score"] > 0
    assert debrief.badges_earned == ["first-flight"]
    assert "POST-FLIGHT REPORT" in debrief.report
    assert snapshot.phase == "complete"
    assert session_id == 1
    assert event_type == "session_completed"
    assert payload["scoring_summary"] == debrief.scoring
    assert payload["badges_earned"] == ["first-flight"]
    assert payload["org_id"] == str(org_id)
    assert payload["session_id"] == 1
    assert payload["graph"] == "scoring"
    assert payload["node"] == "generate_report"
    assert payload["scene_version"] == DEFAULT_SCENE.version
    assert payload["prompt_version"] == DEFAULT_SCENE.version


@pytest.mark.asyncio
async def test_every_event_contains_required_provenance() -> None:
    trace = InMemoryTraceRecorder()
    module = _module(trace=trace, interrupt_before_response=True)
    org_id = uuid.uuid4()
    await _start(module, org_id)
    await module.send(SendTransmissionCommand(org_id, 1, "Request clearance"))
    await module.await_instructor(org_id, 1)

    required = {
        "org_id",
        "session_id",
        "graph",
        "node",
        "scene_version",
        "prompt_version",
    }
    assert [event_type for _, event_type, _ in trace.events] == [
        "session_started",
        "awaiting_instructor",
        "instructor_override",
    ]
    assert all(required <= payload.keys() for _, _, payload in trace.events)
