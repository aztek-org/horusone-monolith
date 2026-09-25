# Architecture Decision Index

Every Architecture Decision Record in `docs/architecture/`, with the decision it
records and its current status. Read this page first to find the ADR that owns
a rule; then read the ADR, which is authoritative for that rule.

| Decision | ADR | Status |
|---|---|---|
| Monorepo | [ADR-001](ADR-001-monorepo-structure.md) | Accepted |
| PostgreSQL | [ADR-002](ADR-002-database-postgresql.md) | Accepted |
| Deployment | [ADR-003](ADR-003-deployment-architecture.md) | Accepted |
| LangGraph topology | [ADR-004](ADR-004-langgraph-multi-agent.md) | Accepted |
| Flight plan pipeline | [ADR-005](ADR-005-flight-plan-pipeline.md) | Accepted |
| Scene/Session split + persistent state | [ADR-006](ADR-006-scene-session-and-persistent-langgraph.md) | Accepted |
| LLM provider adapters | [ADR-007](ADR-007-llm-provider-adapters.md) | Accepted |
| Tenant knowledge + pgvector | [ADR-008](ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) | Accepted |
| Trace | [ADR-009](ADR-009-opentelemetry-and-postgres-trace.md) | Accepted |

No ADR is rejected or deprecated. Two are *partly* superseded, in the sense
that a later ADR narrows or replaces part of them without invalidating the
rest: ADR-004 (by ADR-006 and ADR-007) and ADR-002's scope (by ADR-006,
ADR-008 and ADR-009, which added what this database hosts).

## How the ADRs relate

ADR-001 through ADR-005 predate the work that produced ADR-006 through
ADR-009, and are the more likely to be stale. Where a later decision changes an
earlier one, the later ADR says so — ADR-006 carries an explicit `Supersedes`
header — and the earlier ADR links forward.

- **ADR-006** supersedes part of ADR-004: the orchestrator class, the
  process-local session store, and the module-level LLM global are gone. The
  graph *topology* in ADR-004 still stands.
- **ADR-007** supersedes the provider choice embedded in ADR-004: graph nodes
  now take an injected `LLMModule` and none of them names a provider.
- **ADR-008** extends ADR-002: the same PostgreSQL now hosts pgvector.
- **ADR-009** adds operational telemetry to the provenance trace recorded in
  ADR-006, and does not replace it.

## Rules that live in more than one ADR

| Rule | Owning ADR | Also stated in |
|---|---|---|
| Scene and Session are distinct concepts | [ADR-006](ADR-006-scene-session-and-persistent-langgraph.md) | `CONTEXT.md` (the glossary) |
| 1000-token / 150-token chunking contract | [ADR-008](ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) | `docs/knowledge/INGEST.md` |
| 768-dimension embedding lock | [ADR-008](ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) | `docs/knowledge/INGEST.md` |
| A shipped default that disagrees with an accepted decision is a defect — on every surface that ships the value, not only the code path | [ADR-009](ADR-009-opentelemetry-and-postgres-trace.md) | [ADR-007](ADR-007-llm-provider-adapters.md) |
| Spans carry identifiers and timings, never product content | [ADR-009](ADR-009-opentelemetry-and-postgres-trace.md) | `backend/app/observability/telemetry.py` |
| All SQL is parameterised | [ADR-002](ADR-002-database-postgresql.md) | [ADR-009](ADR-009-opentelemetry-and-postgres-trace.md) |
| Instructor override (HITL) is built and deliberately switched off | [ADR-006](ADR-006-scene-session-and-persistent-langgraph.md) | [ADR-004](ADR-004-langgraph-multi-agent.md), `CONTEXT.md`, `docs/development.md`, issue [#3](https://github.com/martinsgmx/horusone-mvp/issues/3) |
| `GET /api/v1/scenes` always lists the packaged `default-v1`; an unregistered `scene_version` is a 404, never a fallback | [ADR-006](ADR-006-scene-session-and-persistent-langgraph.md) | `backend/app/api/v1/scenes.py` (both route docstrings), `backend/app/services/llm/scenes/registry.py` |
| Legacy `OLLAMA_*` environment names override their grouped `LLM_*` counterparts | — (no ADR; operator rule) | `docs/development.md` ("Legacy environment names"), `backend/app/settings_loader.py`, `backend/app/config.py` |
| Citations are not attached to ATC exchanges; retrieval is wired, the exchange-to-chunk link is deferred | [ADR-008](ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md) | `CONTEXT.md` (the `Citation` term), `backend/app/services/training_sessions/session_module.py` |

## Operator manuals

| Manual | Covers |
|---|---|
| [`docs/knowledge/INGEST.md`](../knowledge/INGEST.md) | Supported formats, the chunking contract, the dimension lock, quotas, publication, tenant isolation, why a failed ingest leaves no audit row, the local adapter |
| [`docs/knowledge/RETRIEVAL.md`](../knowledge/RETRIEVAL.md) | pgvector retrieval, hybrid/RRF search, the fact that **neither** leg ships an index, the HNSW operator workflow and why it must not be partial |
| [`scene-config.example.yaml`](scene-config.example.yaml) | Scene authoring format consumed by `SCENES_PATH` |

`docs/knowledge/INGEST.md` is itself a golden file:
`backend/tests/unit/knowledge/test_ingest_manual.py` ingests it and asserts it
still agrees with the shipped settings.
