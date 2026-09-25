# ADR-006: Scene/Session Split and Persistent LangGraph State

**Status**: Accepted
**Date**: 2026-09-25
**Supersedes**: Part of ADR-004 (in-memory session store, module-level LLM global)

## Context

Horus already has a multi-agent LangGraph pipeline described in
[ADR-004](./ADR-004-langgraph-multi-agent.md), but the implementation does not
yet support the product's target behaviour:

- `HorusOrchestrator` keeps session state in a process-local Python dict
  (`backend/app/services/llm/orchestrator.py`), so a restart loses every live
  session and a second process cannot serve it.
- `backend/app/api/v1/sessions.py` constructs a **new** `HorusOrchestrator()`
  for every scoring call, so the state it needs is never present and scoring
  silently falls back to a zero score.
- The live graph stores its Ollama client in a module-level global
  (`_llm` in `live_session_graph.py`), which prevents more than one model from
  being configured at a time and makes tests order-dependent.
- The domain language is blurred: "scenario", "flight plan", and "session" are
  used interchangeably, but they are three different things.

The product requires multi-agent Scenes, instructor intervention, per-Session
traceability, and the ability to run several backend processes.

## Decision

1. **Scene and Session are distinct concepts.** A Scene is the authored, versioned
   training plan plus initial context. A Session is one user's interaction with
   that Scene. A Flight Plan remains the pilot's own submission and may seed a
   Scene. These terms are recorded in `CONTEXT.md`.

2. **A single Session module owns the lifecycle.** Callers use a narrow interface,
   as built in `backend/app/services/training_sessions/session_module.py`:

   ```python
   class TrainingSessionModule:
       async def start(self, command: StartSessionCommand) -> SessionSnapshot: ...
       async def validate(self, *, user_id, flight_plan, language="en") -> SessionSnapshot: ...
       async def send(self, command: SendTransmissionCommand) -> ExchangeResult: ...
       async def await_instructor(
           self, org_id: UUID, session_id: int, instructor_response: str | None = None
       ) -> ExchangeResult | None: ...
       async def end(self, command: EndSessionCommand) -> Debrief: ...
       async def snapshot(self, org_id: UUID | None, session_id: int) -> SessionSnapshot: ...
   ```

   Note the argument order: `org_id` comes before `session_id`, and
   `validate()` exists for the flight-plan validation route, which has no
   training session yet and persists nothing.

   The interface hides graph construction, checkpointer wiring, tenant checks,
   event emission, and voice-log persistence. Callers never see `HorusState`,
   `thread_id`, or `interrupt_before`.

3. **Session graph state is persisted, not held in process memory.** We use a
   LangGraph checkpointer with a PostgreSQL adapter in production and an
   in-memory adapter in tests. The LangGraph `thread_id` is derived
   deterministically from `(org_id, session_id)` so a tenant can never resume
   another tenant's thread. Redis remains a cache and a rate-limit store; it is
   not the source of truth for graph state.

4. **The LLM is an injected dependency, never constructed in a graph node.**
   Live, validation, and scoring graphs are built by factories that receive an
   LLM module. The module-level `_llm` global is removed. Each backend process
   builds each graph at most once, but not all at the same moment: the live
   Session graph is built once in the `lifespan`
   (`app/main.py:176-184`, inside the `TrainingSessionModule`), while the voice
   pipeline is built **lazily, on the first voice WebSocket connection**
   (`_shared_pipeline`, `app/api/routes/voice.py:83-99`) and published on
   `app.state` for every later connection. The delay is deliberate: building the
   pipeline loads a 145 MB Whisper checkpoint, and a process that never serves
   voice audio should not pay for it. Both properties this decision protects —
   one build per process, not one per request — hold either way.

5. **Every Session step emits a `TrainingSessionEvent`.** The event payload
   carries `scene_version`, `prompt_version`, `graph`, `node`, `llm_provider`,
   `llm_model`, `llm_fallback_used`, `retrieved_chunk_ids`, and `instructor_overridden`.
   These are product data and are read back through
   `GET /api/v1/sessions/{id}/events` and `GET /api/v1/sessions/{id}/replay`.

6. **The in-memory `HorusOrchestrator` is retired** as a caller-facing module once
   the Session module is live.

   *Implemented.* `backend/app/services/llm/orchestrator.py` no longer exists and
   no module exports `HorusOrchestrator`. The composition root
   `backend/app/main.py` builds the `TrainingSessionModule` in its `lifespan` and
   publishes it, with every other collaborator, on `app.state`. In production the
   store is `PostgresSessionStore`; in every other environment it is
   `InMemorySessionStore`, selected by `settings.environment == "production"`.
   `backend/app/services/llm/atc_agent.py` survives as `ATCAgent`, a thin adapter
   over the same live graph, for the `AudioPipeline` interface.

   *Correction to the original text.* The original decision said
   `tests/unit/services/llm/test_atc_agent.py` would be rewritten to cross the
   Session module interface. It was not: that file still tests `ATCAgent`
   directly. The tests that cross the Session module interface are
   `tests/unit/services/test_session_module.py` and
   `tests/integration/test_session_module_postgres.py`, which run the same
   interface against two different checkpointers.

8. **`GET /api/v1/scenes` always lists the packaged default Scene.** This is an
   accepted API change. The composition root registers the packaged `default-v1`
   alongside whatever a configured `SCENES_PATH` provides, whenever that path
   does not already name it (`_build_scene_registry`, `app/main.py:142-149`), so
   the listing always contains a Scene the Session module can actually start.
   `default-v1` therefore **appears after** the operator's own Scenes rather than
   before them, and a client that indexes the list by position sees a new
   trailing entry when `SCENES_PATH` omits the default. Clients must select a
   Scene by its `version`, not by list position.

   The companion rule is that a genuinely unknown `scene_version` is still a
   clean `404`, never a silent substitution. `GET /api/v1/scenes/{version}` calls
   `SceneRegistry.get()`, which raises `KeyError` rather than falling back
   (`app/services/llm/scenes/registry.py:58-60`), and the route turns that into
   `404 Scene '<version>' not found` (`app/api/v1/scenes.py:38-45`). The
   fallback exists only in `SceneRegistry.default()` (`registry.py:66-70`), which
   is for "which Scene do I start when the caller named none" — never for
   "resolve the version the caller asked for". Without that rule a typo would
   hand a client one Scene's context while its request said another, and the
   provenance recorded on the events would name a Scene the client never chose.

## Consequences

### Positive

- A backend restart no longer destroys a live Session.
- Multiple backend processes can serve the same Session.
- Tests cross the same seam production uses: same interface, different checkpointer.
- Model provenance is queryable product data, not log scraping. Which chunks a
  step retrieved is recorded as `retrieved_chunk_ids` on the event; see
  [ADR-008](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) for why
  *citations* are a separate, deliberately deferred piece of work.
- The instructor-override machinery exists, is checkpointed, and is covered by
  tests — the hard part is done even though it is switched off.

### Not yet exposed: instructor override (HITL)

Instructor override is **built, well tested, and deliberately switched off.** It
is not a capability of any running deployment, and this ADR previously listed it
as a shipped Positive. See
[#3](https://github.com/martinsgmx/horusone-mvp/issues/3) for the follow-up.

What is real: `build_live_session_graph(..., interrupt_before_response=True)`
compiles the live graph with `interrupt_before=["generate_atc_response",
"emergency_handler"]`; `TrainingSessionModule.send()` detects the interrupt,
persists `pending_instructor`, emits an `awaiting_instructor` event and returns
`ExchangeResult(atc_response="", pending_instructor=True)`;
`await_instructor(org_id, session_id, instructor_response=None)` releases the
held exchange, recording `instructor_override` with `instructor_overridden=True`
when text was supplied and `False` when the graph's own response was released;
and the pending state is checkpointed, so it survives a backend restart.

What is not real: **no route calls `await_instructor`** — `grep -rn
await_instructor backend/app/api/` returns nothing — and **nothing sets the
flag**. `interrupt_before_response` is a constructor argument of
`TrainingSessionModule` (`app/services/training_sessions/session_module.py:61`)
defaulting to `False`; the composition root `app/main.py:157-165` does not pass
it, no `Settings` field sources it, and no `.env` template declares it.
`ATCAgent` passes `False` explicitly. So in every deployment
`instructor_overridden` is always `False` and the `awaiting_instructor` event is
never emitted.

**Turning it on is three pieces of work, not a flag flip:**

1. a configuration field — a `Settings` key read at composition-root time and
   passed as `interrupt_before_response`, guarded by the template/code-default
   agreement test that ADR-009's "Shipped defaults are part of the contract"
   requires for any new default;
2. an authorized response route that calls `await_instructor`, behind the
   existing active-seat check, the `instructor` seat role, and the tenant scoping
   every other session route uses — today the method exists with no endpoint, so
   a held exchange can never be released;
3. a frontend pending state, because a held exchange returns an empty
   `atc_response` and the pilot currently hears silence.

Until all three land, do not describe HITL as available. Both failure directions
are safety-relevant: a student pilot must never receive an AI response an
instructor believed they had reviewed, and a session that stops responding with
nothing to show for it is why the feature stays off.

### Negative

- A PostgreSQL migration is required for LangGraph checkpoint tables.
- The Session module is a larger interface surface than the current three
  orchestrator methods, and callers must learn `StartSessionCommand` /
  `SendTransmissionCommand` / `EndSessionCommand`.
- HITL's pending state is the one part of this ADR the frontend has not been
  asked to render, because HITL is switched off. That debt is deferred, not
  paid.

### Neutral

- `HorusState` remains the graph-internal state; it is simply no longer shared
  with callers.
- ADR-004 remains valid for the validation/live/scoring graph topology; this ADR
  only changes how those graphs are built, resumed, and traced.

## References

- [ADR-002: Database Selection](./ADR-002-database-postgresql.md)
- [ADR-004: LangGraph Multi-Agent Architecture](./ADR-004-langgraph-multi-agent.md)
- [ADR-007: LLM Provider Adapters](./ADR-007-llm-provider-adapters.md)
- [ADR-009: OpenTelemetry and Postgres Trace](./ADR-009-opentelemetry-and-postgres-trace.md)
- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
