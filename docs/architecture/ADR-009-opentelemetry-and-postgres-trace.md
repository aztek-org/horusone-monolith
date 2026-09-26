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

5. **Correlation keys.** The *span* half is delivered: OTel instrumentation
   puts `trace_id` on every span, and `span_for_session(session_id, org_id)`
   opens a `session.exchange` span tagged with `session_id` and `org_id`. The
   *log-line* half is **not** delivered — see "the log-line half is not wired"
   below. Every provenance payload carries `scene_version` and `prompt_version`.

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
when nothing errors — and the guard must cover every surface that ships the
value, not only the code path.** Four times, a value that shipped contradicted an
accepted decision. None of the four raised, failed a test, or appeared in a
log:

| What shipped | The decision it contradicted | ADR |
|---|---|---|
| `KnowledgeSettings.chunk_overlap = 200` | the fixed 1000/150 chunking contract | ADR-008 |
| `TraceSettings.retention_days = 30` | 90-day provenance retention | this ADR |
| `temperature=0.7` in `atc_agent.py`, `temperature=0.3` in `live_session_graph.py`, and a hardcoded HITL flag, all at the call site | provider choice and Scene overrides belong in config, not at a call site | ADR-007 |
| `KNOWLEDGE_CHUNK_OVERLAP=200` in `backend/.env.example` and `backend/.env.prod.example`, **after** the code default was corrected to 150 | the same 1000/150 chunking contract | ADR-008 |

The first two are config defaults and the third is the same failure mode in a
hardcoded literal. **The fourth is the instructive one**, and it is the reason
the rule is stated in its generalisable form rather than the narrow one this
section used to carry.

The first three were each caught by a **config regression test asserting the
concrete value**. A test that says `settings.knowledge.chunk_overlap is not
None` passes just as happily at 200 as at 150; what catches the drift is
asserting `150` literally. But that remedy is *structurally incapable* of
catching the fourth instance, and the fourth instance is the one that reached
operators. `backend/.env.example` is copied to `backend/.env` by
`setup.sh:250-253`, and `docs/development.md` tells every production deployment
to copy `backend/.env.prod.example`. A test that constructs `Settings(...)`
cannot see a template: the template is not an argument, not an import, and not a
code path. So the drift that mattered most to real deployments was precisely the
drift the guard could not reach, and the code default had already been fixed,
which made the remaining copy look like a cosmetic leftover rather than a live
defect. The consequence had already been committed to the `ingest_events` table
in every environment created from those two files.

The generalisable form, therefore:

- **A default that silently disagrees with an accepted decision is a defect even
  when nothing errors.** Nothing raising is not evidence that a value is right.
- **The guard must cover every surface that ships the value.** A value reaches a
  deployment through the code default, through a `.env` template an operator
  copies, and through a document an operator reads. A guard on one surface is a
  guard on that surface only, and a value that is correct on the guarded surface
  and wrong on an unguarded one is still wrong where it is wrong.
- **Assert the concrete value, and assert that two surfaces agree.** Not that a
  value exists, and not that one surface is self-consistent.

What now guards each:

| Surface | Guard |
|---|---|
| code default (chunking) | `backend/tests/unit/test_config.py::test_knowledge_chunking_defaults_are_stable` — asserts `1000` and `150` literally |
| code default (retention) | `backend/tests/unit/test_config.py::test_trace_retention_default_matches_adr_contract` — asserts `90` literally |
| code default (external fallback) | `backend/tests/unit/test_config.py::test_external_fallback_default_matches_adr_contract` — asserts `False` literally |
| **the templates operators copy** | `backend/tests/unit/test_config.py::test_shipped_templates_and_code_defaults_agree` — every shipped template, every configured key, each value equal to the code default; plus `test_shipped_templates_match_the_chunking_contract` for the two templates that `setup.sh` and the production runbook tell operators to copy, and `test_shipped_templates_match_the_trace_retention_contract` |
| **the operator manual** | `backend/tests/unit/knowledge/test_ingest_manual.py` — ingests `docs/knowledge/INGEST.md` through the real extraction and chunking path and asserts the manual's stated contract is derived from the live settings object, so the doc and the code cannot drift apart |
| the telemetry name policy | `backend/tests/unit/test_telemetry.py::test_query_and_fragment_named_attributes_are_removed` and `::test_numeric_port_attributes_survive_while_string_hosts_are_scrubbed` |

When you add a decision, add the literal value it fixes, the test that holds it,
**and every surface through which that value reaches a deployment.** If a
template must legitimately differ from the code default, do not weaken the check:
drop the key from the table and add a named test asserting the documented reason
for the divergence.

This rule is owned here rather than in ADR-007 or ADR-008 because every instance
was found the same way — a shipped value disagreeing with a written decision, and
nothing in the code that consumed the value being wrong.

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
- **The removal is by name token, not by exception, so it is wider than
  exception text.** The `message` term in `_CALLER_TEXT_TERMS` matches
  `error.message` and `log.record.message` as well, so an OTel Logs bridge over
  these spans loses the log body too. Anything a caller would have found in a
  span attribute whose name contains `message` is gone.
- **What the name-token policy does *not* remove is the numeric port
  attributes.** `net.host.port`, `server.port` and `client.port` all match
  `_URL_BEARING_TERMS` (`host`, `server`, `client`) and all survive **only**
  because `_scrub_url_value` returns any `int`/`float`/`bool` untouched — a
  number cannot contain a `?` or `#` delimiter, so there is nothing to strip.
  That single type test is the entire reason those three attributes are in the
  span. It is a property of the value, not of the name, so a port that arrived
  as a string would be scrubbed to its prefix.
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

### `db.statement` is kept; `db.query.text` is deleted

The two halves of this are not the same, and an earlier version of this section
said the scrubber "has no rule for `db.statement` or its successor
`db.query.text`, and deliberately does not touch them". Only the first half was
true.

- **`db.statement` is kept, and deliberately.** Its tokens are
  `{db, statement}`: no term in `_URL_BEARING_TERMS` or `_CALLER_TEXT_TERMS`
  matches, so `_scrub_attributes` leaves it alone. The asyncpg instrumentation
  populates `db.statement` on database spans: its stability mapping is empty, so
  the mode resolves to `DEFAULT`, and `_set_db_statement` reports the old
  convention for every mode except `HTTP` and `DATABASE`. The attribute carries
  the SQL text as sent to the server.
- **`db.query.text` is deleted, and not by choice.** Its tokens are
  `{db, query, text}`; `query` is in `_CALLER_TEXT_TERMS`, so the attribute is
  removed outright. This is the name the OTel database semantic conventions
  moved *to*, so any instrumentation that adopts it loses the statement text
  rather than exposing it. The deletion is correct — an unscrubbed statement
  attribute would be the leak this scrubber exists to prevent — but it means
  "we keep `db.statement`" is a fact about the *installed asyncpg
  instrumentation's* naming, not a property of the policy, and it will change
  silently if the instrumentation catches up with the conventions.

`db.statement` being safe is safe **only because every statement in
`backend/app/` is parameterised.** Verified by search: there is no f-string,
`%`-format, or `.format()` SQL construction anywhere under `backend/app/`, and
the only literal `text()` calls are constants — `text("SELECT 1")` in
`app/api/routes/health.py` and `text("org_id IS NULL")` /
`text("org_id IS NOT NULL")` in `app/models/gamification.py`. Everything else
goes through SQLAlchemy expression binding, so an interpolated value never
reaches the statement text.

Neither `db.statement` nor `db.query.text` appears in
`backend/tests/unit/test_telemetry.py`, so the classification above is verified
by reading `_attribute_tokens` and `_CALLER_TEXT_TERMS` and running them, not by
a test that would fail if the term sets changed. Adding the two names to
`test_query_and_fragment_named_attributes_are_removed` (for
`db.query.text`) and to `test_route_template_and_caller_bearing_attributes_survive_scrubbing`
(for `db.statement`) would make the asymmetry a held property rather than a
reading of the source. Until then, treat it as documented-and-verified-once, not
as guarded.

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

### The log-line half of decision 5 is not wired at all

Decision 5 originally promised that *every log line* carries `org_id`,
`session_id`, and `trace_id`. None of the three is delivered.

- **No `logger.*` call under `backend/app/` passes `extra=`.** All ~175 logger
  calls format `org_id` or `session_id` into the message *string* where they have
  it (`app/api/v1/scenarios.py:54`, `app/api/v1/admin.py:441`,
  `app/api/v1/gamification.py:100`, `app/api/routes/voice.py:298`, and so on),
  which is prose a log aggregator can grep, not structured fields it can filter
  on. Most calls carry neither.
- **No `trace_id` is injected into a `LogRecord`.** There is no logging filter,
  formatter, or processor anywhere in `app/` that adds one;
  `app/main.py:47-50` installs a plain `logging.basicConfig` with
  `format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"`. An
  operator cannot pivot from a trace to the log lines of the same request, which
  is the whole point of the promise.

So the correlation story is currently: spans carry `trace_id` and
`session.exchange` spans carry `session_id`/`org_id`, but only for the
instrumentation's own spans; log lines carry a message string and, sometimes, a
tenant id rendered into it. Closing this means a `logging.Filter` that reads the
active span and injects the keys, plus `extra=` at the call sites that have a
tenant or session in hand — and, given the accepted-decision default above, a
regression test that asserts a log record actually carries the fields rather than
a test that the formatter string mentions them.

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
