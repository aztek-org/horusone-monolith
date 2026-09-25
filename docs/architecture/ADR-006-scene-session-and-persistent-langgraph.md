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

2. **A single Session module owns the lifecycle.** Callers use a narrow interface:

   ```python
   class TrainingSessionModule(Protocol):
       async def start(self, command: StartSessionCommand) -> SessionSnapshot: ...
       async def send(self, command: SendTransmissionCommand) -> ExchangeResult: ...
       async def await_instructor(self, session_id: int, org_id: UUID) -> ExchangeResult | None: ...
       async def end(self, command: EndSessionCommand) -> Debrief: ...
       async def snapshot(self, session_id: int, org_id: UUID) -> SessionSnapshot: ...
   ```

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
   builds its graphs once at startup.

5. **Every Session step emits a `TrainingSessionEvent`.** The event payload
   carries `scene_version`, `prompt_version`, `graph`, `node`, `llm_provider`,
   `llm_model`, `llm_fallback_used`, `retrieved_chunk_ids`, and `instructor_overridden`.
   These are product data and are read back through
   `GET /api/v1/sessions/{id}/events` and `GET /api/v1/sessions/{id}/replay`.

6. **The in-memory `HorusOrchestrator` is retired** as a caller-facing module once
   the Session module is live. `backend/tests/unit/services/llm/test_atc_agent.py`
   is rewritten to cross the Session module interface rather than a private graph.

## Consequences

### Positive

- A backend restart no longer destroys a live Session.
- Multiple backend processes can serve the same Session.
- Instructor override (HITL) becomes resumable and auditable.
- Tests cross the same seam production uses: same interface, different checkpointer.
- Citation and model provenance become queryable product data, not log scraping.

### Negative

- A PostgreSQL migration is required for LangGraph checkpoint tables.
- The Session module is a larger interface surface than the current three
  orchestrator methods, and callers must learn `StartSessionCommand` /
  `SendTransmissionCommand` / `EndSessionCommand`.
- HITL now has a real pending state, which the frontend must render.

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
