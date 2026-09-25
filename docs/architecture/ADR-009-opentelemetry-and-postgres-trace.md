# ADR-009: OpenTelemetry and Postgres Trace

**Status**: Accepted
**Date**: 2026-09-25

## Context

Horus needs a trace that lets an instructor answer "why did the ATC say this?"
for every exchange in a Session. We considered LangSmith, Langfuse, and other
commercial tracing platforms. They require paid licences for meaningful volume,
send prompt and transcript data to a third party, and make the product
dependent on an external service for a feature we consider product data.

We already have `TrainingSessionEvent` rows in PostgreSQL, read back through
`GET /api/v1/sessions/{id}/events` and included in the replay payload. That
gives us a durable, tenant-scoped, already-authorized place to store trace.

## Decision

1. **Provenance is product data and lives in PostgreSQL.** Every Session step
   appends a `TrainingSessionEvent` whose `event_payload` carries the fields
   listed in [ADR-006](./ADR-006-scene-session-and-persistent-langgraph.md).
   The replay endpoint remains the single read seam for instructors.

2. **Operational telemetry uses OpenTelemetry.** We emit OTel spans and
   structured JSON logs for latency, error rate, provider usage, and cost
   counters. The OTel exporter is a deployment choice, not a product
   dependency: the backend works with a console exporter, a collector on the
   same VPS, or an OTLP endpoint.

3. **No paid or licensed tracing platform is required.** The backend has no
   runtime dependency on LangSmith, Langfuse, or any hosted tracing service.

4. **Retention.** Provenance rows are retained for 90 days by default
   (`TRACE_RETENTION_DAYS=90`), then pruned by a scheduled job. Operational
   spans follow the deployment's own log retention.

5. **Correlation keys.** Every log line and span carries `org_id`,
   `session_id`, and `trace_id`; every provenance payload carries
   `scene_version` and `prompt_version`.

## Consequences

### Positive

- Instructor trace survives backend restarts and vendor outages.
- Tenant authorization is enforced once, by the existing session access check.
- No licence cost, no data leaving the VPS, no vendor lock.

### Negative

- Building an instructor-facing trace view is our work, not a vendor's.
- Spans and provenance can drift; we reconcile by deriving spans from the same
  event rows where practical.

### Neutral

- OTel is a lightweight addition; it does not change the Session interface.

## Operational notes

Retention is invoked by the host scheduler, not by an in-process scheduler. Set
`TRACE_RETENTION_DAYS=90` in the backend environment and install this cron entry:

```cron
17 3 * * * cd /opt/horus/backend && .venv/bin/python scripts/prune_session_events.py
```

The script commits one bulk delete and prints the number of expired event rows
removed. Monitor cron output and alert on non-zero exit status.

### Shipped defaults are part of the contract

**A default that silently disagrees with an accepted decision is a defect, even
when nothing errors.** Three times, a value that shipped contradicted an
accepted decision. None of the three raised, failed a test, or appeared in a
log:

| What shipped | The decision it contradicted | ADR |
|---|---|---|
| `KnowledgeSettings.chunk_overlap = 200` | the fixed 1000/150 chunking contract | ADR-008 |
| `TraceSettings.retention_days = 30` | 90-day provenance retention | this ADR |
| `temperature=0.7` in `atc_agent.py`, `temperature=0.3` in `live_session_graph.py`, and a hardcoded HITL flag, all at the call site | provider choice and Scene overrides belong in config, not at a call site | ADR-007 |

The first two are config defaults; the third is the same failure mode in a
hardcoded literal. The remedy that worked in every case was a **config
regression test asserting the concrete value**, not merely that a value exists.
A test that says `settings.knowledge.chunk_overlap is not None` passes just as
happily at 200 as at 150. What catches the drift is:

- `backend/tests/unit/test_config.py::test_knowledge_chunking_defaults_are_stable`
  — asserts `1000` and `150` literally.
- `backend/tests/unit/test_config.py::test_trace_retention_default_matches_adr_contract`
  — asserts `90` literally.
- `backend/tests/unit/knowledge/test_ingest_manual.py` — ingests
  `docs/knowledge/INGEST.md` and asserts the manual's stated contract is derived
  from the live settings object, so the doc and the code cannot drift apart.

The third is the generalisable form: assert that a *document* and a *default*
agree, not that either one exists. When you add a decision, add the literal
value it fixes and the test that holds it. This rule is owned here rather than in
ADR-007 or ADR-008 because all three instances were found the same way — an
implementation disagreeing with a written decision — and none of them was a bug
in the code that consumed the value.

### Exception text is deleted from spans — interim, not settled

`_QueryStringScrubber` deletes `exception.message`, `exception.stacktrace`, and
`traceback` — in practice every attribute whose name contains the term
`message` — from every exported span. This is a **fail-closed interim measure**,
not a settled trade. A review of the policy explicitly rejected the framing that
deletion is the only option; it is the option that is safe today.

- **Why it is there.** An exception message that interpolates caller free text
  has no query delimiter to truncate at. Every other value in a span is cut at
  the first `?`/`#`; an exception message is usually
  `f"no flight plan for {user_text}"`, where the caller text arrives before any
  delimiter. Truncating is impossible, so the value is removed.
- **What it costs.** Traces from this backend carry `exception.type`, the span
  status, and the HTTP status, but **no exception message and no stack trace**.
  An engineer debugging an incident reads the trace for which request failed and
  the application log for why.
- **The root cause is product code, not the telemetry module.** The remedy is a
  convention: **exception messages are built from constants and
  `type(e).__name__` only.** Never interpolate a request value into an
  exception message. Once that holds, an allowlist by exception type can keep
  the safe messages and the blanket deletion goes away.
- **Why span name and status description are only truncated, not deleted.** Both
  are code-controlled identifiers — a node name, a graph edge, a status literal —
  not free text. The same delimiter rule therefore applies and no information is
  lost. The asymmetry with exception text is deliberate: what differs is *who
  controls the value*, not how it is shaped.
- **Operators are told at deploy time.** `configure_telemetry` logs a warning
  once per process saying exception text is removed and what the cost is, so
  this is learned from the deployment's own log rather than from a trace that
  stopped being useful mid-incident.

### `db.statement` is not scrubbed, and parameterisation is why that is safe

The scrubber has no rule for `db.statement` or its successor `db.query.text`,
and deliberately does not touch them. The asyncpg instrumentation populates
`db.statement` on database spans: its stability mapping is empty, so the mode
resolves to `DEFAULT`, and `_set_db_statement` reports the old convention for
every mode except `HTTP` and `DATABASE`. Those attributes carry the SQL text as
sent to the server.

That is safe today **only because every statement in `backend/app/` is
parameterised.** Verified by search: there is no f-string, `%`-format, or
`.format()` SQL construction anywhere under `backend/app/`, and the only literal
`text()` calls are constants — `text("SELECT 1")` in `app/api/routes/health.py`
and `text("org_id IS NULL")` / `text("org_id IS NOT NULL")` in
`app/models/gamification.py`. Everything else goes through SQLAlchemy expression
binding, so an interpolated value never reaches the statement text.

**This is a constraint future changes must preserve.** A single
`await db.execute(text(f"... {value} ..."))` under `backend/app/` would put caller
text into an unscrubbed span attribute and defeat the privacy policy without any
test failing. If a query genuinely cannot be expressed as a bound expression, the
answer is a `db.statement` rule in the scrubber — not a bypass.

### `span_for_session` has no production caller yet

`span_for_session(session_id, org_id)` is exported from `app.observability` and
opens a `session.exchange` span tagged with `session_id` and `org_id` — and
nothing else; `org_id` is omitted rather than nulled when unknown. It is a
required interface with no wiring: the only callers are in
`backend/tests/unit/test_telemetry.py`. **Do not read the Session module as
instrumented — it is not.**

Decision 5's promise that every span carries the correlation keys is therefore
only realised for spans produced by the OTel FastAPI and asyncpg
instrumentations; no product spans are emitted yet. Wiring `span_for_session`
into `app/services/training_sessions/session_module.py` is the outstanding piece
of this ADR.

### The OTLP exporter is an optional extra

`opentelemetry-exporter-otlp-proto-http` is declared under the `otel` extra in
`backend/pyproject.toml`, not in the base dependencies. A normal `uv sync` does
**not** install it, so:

- Setting `OTEL_EXPORTER_OTLP_ENDPOINT` without the extra is a configuration
  state, not an error: `_build_exporter` warns (naming the host, never the
  credentials) and falls back to the console exporter rather than leaving the
  deployment silently untraced.
- The OTLP happy path is **unexercised in a normal install**:
  `test_otlp_endpoint_constructs_exporter_when_optional_extra_is_present` uses
  `pytest.importorskip` and is skipped unless the extra is installed. The
  degradation path *is* covered unconditionally, by forcing the import to fail.
- To exercise the OTLP path — locally or in CI — install the extra:

  ```bash
  cd backend && uv sync --extra otel
  ```

  CI that does not install it is not asserting that traces reach a collector.

## References

- [ADR-006: Scene/Session Split and Persistent LangGraph State](./ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
