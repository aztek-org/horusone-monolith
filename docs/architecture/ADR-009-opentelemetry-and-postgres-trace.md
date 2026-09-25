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

## References

- [ADR-006: Scene/Session Split and Persistent LangGraph State](./ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
