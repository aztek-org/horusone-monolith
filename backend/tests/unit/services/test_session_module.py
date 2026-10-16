"""Behavioral tests for the persisted training Session module."""

import uuid
from dataclasses import replace

import pytest

from app.knowledge.retrieval.fake import FakeRetriever
from app.knowledge.types import RetrievedChunk
from app.llm.adapters.fake_adapter import FakeAdapter
from app.services.llm.scenes.default_scene import DEFAULT_SCENE
from app.services.llm.scenes.registry import SceneConfig, SceneRegistry
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
    db_session_factory: type[_NoDb] = _NoDb,
    require_org: bool = True,
    scene: SceneConfig = DEFAULT_SCENE,
    **kwargs: object,
) -> TrainingSessionModule:
    return TrainingSessionModule(
        store or InMemorySessionStore(),
        trace or InMemoryTraceRecorder(),
        SceneRegistry({scene.version: scene}),
        FakeAdapter(),
        db_session_factory=db_session_factory,
        require_org=require_org,
        **kwargs,
    )


async def _start(
    module: TrainingSessionModule,
    org_id: uuid.UUID | None,
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


def test_module_passes_weather_service_to_validation_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composed module must thread its weather service into validation."""
    seen: dict[str, object] = {}

    def _build(knowledge: object, weather: object = None) -> object:
        seen["knowledge"] = knowledge
        seen["weather"] = weather
        return object()

    monkeypatch.setattr(
        "app.services.training_sessions.session_module.build_validation_graph",
        _build,
    )
    weather = object()

    _module(weather=weather)

    assert seen == {"knowledge": None, "weather": weather}


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
    assert released.exchange_count == 1


@pytest.mark.asyncio
async def test_instructor_override_records_actual_text_and_completes_exchange() -> None:
    store = InMemorySessionStore()
    trace = InMemoryTraceRecorder()
    org_id = uuid.uuid4()
    normal_module = _module(store=store, trace=trace)
    await _start(normal_module, org_id)
    previous = await normal_module.send(
        SendTransmissionCommand(org_id, 1, "Tower, request taxi")
    )

    review_module = _module(
        store=store,
        trace=trace,
        interrupt_before_response=True,
    )
    interrupted = await review_module.send(
        SendTransmissionCommand(org_id, 1, "Tower, ready for departure")
    )
    released = await review_module.await_instructor(
        org_id,
        1,
        "Tower, taxi via Alpha, hold short runway 27.",
    )

    assert previous.atc_response == "Say again, transmission unclear."
    assert interrupted.pending_instructor is True
    assert released is not None
    assert released.atc_response == "Tower, taxi via Alpha, hold short runway 27."
    assert released.exchange_count == 2
    snapshot = await review_module.snapshot(org_id, 1)
    assert snapshot.state["pilot_message"] == "Tower, ready for departure"
    assert snapshot.state["atc_response"] == (
        "Tower, taxi via Alpha, hold short runway 27."
    )
    _, event_type, payload = trace.events[-1]
    assert event_type == "instructor_override"
    assert payload["atc_response"] == (
        "Tower, taxi via Alpha, hold short runway 27."
    )
    assert payload["instructor_overridden"] is True


@pytest.mark.asyncio
async def test_instructor_release_uses_graph_response_without_override() -> None:
    trace = InMemoryTraceRecorder()
    module = _module(trace=trace, interrupt_before_response=True)
    org_id = uuid.uuid4()
    await _start(module, org_id)
    await module.send(SendTransmissionCommand(org_id, 1, "Request clearance"))

    released = await module.await_instructor(org_id, 1)

    assert released is not None
    assert released.atc_response == "Say again, transmission unclear."
    assert released.exchange_count == 1
    assert released.provider == "fake"
    _, event_type, payload = trace.events[-1]
    assert event_type == "instructor_override"
    assert payload["atc_response"] == "Say again, transmission unclear."
    assert payload["instructor_overridden"] is False


@pytest.mark.asyncio
async def test_end_rejects_session_pending_instructor() -> None:
    module = _module(interrupt_before_response=True)
    org_id = uuid.uuid4()
    await _start(module, org_id)
    await module.send(SendTransmissionCommand(org_id, 1, "Request clearance"))

    with pytest.raises(SessionPendingInstructorError):
        await module.end(EndSessionCommand(org_id, 1))


@pytest.mark.asyncio
async def test_emergency_transmission_pauses_for_instructor_review() -> None:
    module = _module(interrupt_before_response=True)
    org_id = uuid.uuid4()
    await _start(module, org_id)

    result = await module.send(
        SendTransmissionCommand(org_id, 1, "MAYDAY MAYDAY engine failure")
    )

    assert result.pending_instructor is True
    assert result.atc_response == ""
    assert result.is_emergency is True
    assert result.exchange_count == 0


@pytest.mark.asyncio
async def test_require_org_false_completes_full_session_without_tenant() -> None:
    module = _module(require_org=False, interrupt_before_response=True)

    await _start(module, None)
    interrupted = await module.send(
        SendTransmissionCommand(None, 1, "Tower, request taxi")
    )
    released = await module.await_instructor(None, 1)
    snapshot = await module.snapshot(None, 1)
    debrief = await module.end(EndSessionCommand(None, 1))

    assert interrupted.pending_instructor is True
    assert released is not None
    assert released.exchange_count == 1
    assert snapshot.exchange_count == 1
    assert debrief.scoring["overall_score"] > 0


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
async def test_scene_snapshot_update_is_scoped_to_organization() -> None:
    class RecordingDb(_NoDb):
        instances: list["RecordingDb"] = []

        def __init__(self) -> None:
            super().__init__()
            self.statements: list[object] = []
            RecordingDb.instances.append(self)

        async def execute(self, statement: object) -> None:
            self.statements.append(statement)

    org_id = uuid.uuid4()
    module = _module(db_session_factory=RecordingDb)
    await _start(module, org_id)

    update = RecordingDb.instances[0].statements[0]
    compiled = update.compile()
    assert "training_sessions.org_id" in str(compiled)
    assert org_id in compiled.params.values()


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


class _RecordingRetriever:
    """Records the queries the validation graph's retrieval node issues."""

    def __init__(self) -> None:
        self.queries: list[object] = []

    async def search(self, query: object) -> list[object]:
        self.queries.append(query)
        return []


@pytest.mark.asyncio
async def test_start_scopes_retrieval_to_the_session_tenant() -> None:
    """A started session retrieves as its own tenant, not as a global reader."""
    retriever = _RecordingRetriever()
    org_id = uuid.uuid4()
    module = _module(knowledge=retriever)

    await _start(module, org_id)

    assert len(retriever.queries) == 1
    assert retriever.queries[0].org_id == org_id


@pytest.mark.asyncio
async def test_start_scopes_retrieval_to_the_scenes_knowledge_refs() -> None:
    """A Scene's ``knowledge_refs`` reach the query instead of being dropped."""
    retriever = _RecordingRetriever()
    scene = replace(DEFAULT_SCENE, knowledge_refs=["keflavik-approach.md"])
    org_id = uuid.uuid4()
    module = _module(knowledge=retriever, scene=scene)

    await _start(module, org_id)

    assert retriever.queries[0].knowledge_refs == ["keflavik-approach.md"]


@pytest.mark.asyncio
async def test_start_without_a_tenant_retrieves_only_global_knowledge() -> None:
    """``require_org=False`` stays fail-closed rather than reaching a tenant."""
    retriever = _RecordingRetriever()
    module = _module(knowledge=retriever, require_org=False)

    await _start(module, None)

    assert retriever.queries[0].org_id is None


@pytest.mark.asyncio
async def test_validate_scopes_retrieval_to_a_tenant_when_the_caller_knows_it() -> None:
    """The flight-plan route can opt into tenant-scoped retrieval."""
    retriever = _RecordingRetriever()
    module = _module(knowledge=retriever)
    org_id = uuid.uuid4()

    await module.validate(
        user_id=None,
        flight_plan={"departure_icao": "KLAX", "arrival_icao": "KSFO"},
        org_id=org_id,
    )

    assert retriever.queries[0].org_id == org_id


@pytest.mark.asyncio
async def test_validate_without_a_tenant_retrieves_only_global_knowledge() -> None:
    """The tenant-less validate path is explicit, and global-only by design.

    Retrieval with no tenant resolves to ``org_id IS NULL``, so a flight plan
    checked without one can never reach another tenant's private manuals.
    """
    retriever = _RecordingRetriever()
    module = _module(knowledge=retriever)

    await module.validate(
        user_id=None,
        flight_plan={"departure_icao": "KLAX", "arrival_icao": "KSFO"},
    )

    assert retriever.queries[0].org_id is None
    assert retriever.queries[0].knowledge_refs == []


@pytest.mark.asyncio
async def test_validate_runs_the_graph_without_persisting_state() -> None:
    """``validate`` returns a snapshot of a flight-plan check and stores nothing."""
    store = InMemorySessionStore()
    trace = InMemoryTraceRecorder()
    module = _module(store=store, trace=trace)
    user_id = uuid.uuid4()

    snapshot = await module.validate(
        user_id=user_id,
        flight_plan={
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

    assert snapshot.session_id == 0
    assert snapshot.state["user_id"] == str(user_id)
    assert snapshot.state["validation_results"]
    assert "validation_passed" in snapshot.state
    assert await store.load(uuid.UUID(int=0), 0) is None
    assert trace.events == []


class _ConfigRecordingGraph:
    """Stand-in live graph that records the LangGraph config it is handed."""

    def __init__(self, configs: list[object], interrupts: bool) -> None:
        self.configs = configs
        self.interrupts = interrupts

    async def astream(self, state: dict, config: object = None, **_kwargs: object):
        self.configs.append(config)
        if self.interrupts:
            yield "updates", {"__interrupt__": ("generate_atc_response",)}
        yield "values", {
            **state,
            "atc_response": "N123AB cleared",
            "exchange_count": 1,
            "pending_instructor": False,
        }


def _module_with_recording_graph(monkeypatch, configs: list[object]) -> TrainingSessionModule:
    monkeypatch.setattr(
        "app.services.training_sessions.session_module.build_live_session_graph",
        lambda _llm, _scene, interrupts, _knowledge=None: _ConfigRecordingGraph(
            configs, interrupts
        ),
    )
    return _module()


@pytest.mark.asyncio
async def test_live_graph_runs_on_the_tenant_scoped_thread(monkeypatch) -> None:
    """The live graph must be invoked with the tenant's checkpoint thread_id."""
    configs: list[object] = []
    module = _module_with_recording_graph(monkeypatch, configs)
    org_id = uuid.uuid4()
    await _start(module, org_id)

    await module.send(SendTransmissionCommand(org_id, 1, "Tower, request taxi"))

    assert configs == [{"configurable": {"thread_id": f"{org_id}:1"}}]


@pytest.mark.asyncio
async def test_thread_id_separates_tenants_sharing_a_session_id(monkeypatch) -> None:
    """Two tenants running the same session_id must not share a checkpoint thread."""
    configs: list[object] = []
    first = uuid.uuid4()
    second = uuid.uuid4()

    tenant_a = _module_with_recording_graph(monkeypatch, configs)
    await _start(tenant_a, first)
    await tenant_a.send(SendTransmissionCommand(first, 1, "Tower, request taxi"))

    tenant_b = _module_with_recording_graph(monkeypatch, configs)
    await _start(tenant_b, second)
    await tenant_b.send(SendTransmissionCommand(second, 1, "Tower, request taxi"))

    thread_ids = [config["configurable"]["thread_id"] for config in configs]
    assert thread_ids == [f"{first}:1", f"{second}:1"]
    assert thread_ids[0] != thread_ids[1]


@pytest.mark.asyncio
async def test_await_instructor_runs_on_the_tenant_scoped_thread(monkeypatch) -> None:
    """The instructor release path must use the same tenant-scoped thread."""
    configs: list[object] = []
    module = _module(interrupt_before_response=True)
    monkeypatch.setattr(
        "app.services.training_sessions.session_module.build_live_session_graph",
        lambda _llm, _scene, interrupts, _knowledge=None: _ConfigRecordingGraph(
            configs, interrupts
        ),
    )
    org_id = uuid.uuid4()
    await _start(module, org_id)
    await module.send(SendTransmissionCommand(org_id, 1, "request clearance"))
    configs.clear()

    await module.await_instructor(org_id, 1)

    assert configs == [{"configurable": {"thread_id": f"{org_id}:1"}}]


@pytest.mark.asyncio
async def test_send_returns_citations_for_retrieved_chunks() -> None:
    """A completed exchange carries the chunks its Scene knowledge retrieved."""
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        org_id=None,
        title="Ground Operations",
        content="Tower request taxi clearance standard phraseology",
        score=3.0,
        page=2,
        section="Ground",
        char_start=0,
        char_end=50,
        source_filename="sop.md",
    )
    retriever = FakeRetriever()
    await retriever.add(chunk)
    scene = replace(DEFAULT_SCENE, knowledge_refs=["sop.md"])
    module = _module(scene=scene, knowledge=retriever)
    org_id = uuid.uuid4()
    await _start(module, org_id)

    result = await module.send(SendTransmissionCommand(org_id, 1, "Tower, request taxi"))

    assert [citation.chunk_id for citation in result.citations] == [chunk.chunk_id]
    assert result.citations[0].page == 2
    assert result.citations[0].snippet.startswith("Tower request taxi")
