# Horus Documentation Index

This directory uses a single-source-of-truth documentation model to keep guides reliable and
maintainable as the platform grows.

## Canonical documents

| File | Purpose |
|------|---------|
| `docs/development.md` | Main developer guide for setup, architecture overview, testing, deployment, and troubleshooting |
| `docs/OLLAMA_SETUP.md` | Ollama deployment and configuration scenarios (local, shared, remote) |
| `docs/architecture/ARCHITECTURE-INDEX.md` | Decision → ADR → status table; start here for "who decided this?" |
| `docs/architecture/ADR-*.md` | Architecture Decision Records (ADRs) |
| `docs/knowledge/INGEST.md` | Operator manual: knowledge ingest formats, chunking contract, dimension lock, tenancy |
| `docs/knowledge/RETRIEVAL.md` | Operator manual: pgvector retrieval, HNSW operator workflow, hybrid search |

## Documentation conventions

1. Keep setup and onboarding in `docs/development.md`.
2. Keep architecture decisions in ADR files under `docs/architecture/`, and add
   every new ADR to `docs/architecture/ARCHITECTURE-INDEX.md` in the same change.
3. Prefer links to canonical docs instead of repeating long setup/status content in new files.
4. Remove temporary or one-off status docs after their relevant content is merged into canonical docs.
5. `docs/knowledge/INGEST.md` is a golden file: it is ingested by
   `backend/tests/unit/knowledge/test_ingest_manual.py`, which asserts it still
   agrees with the shipped chunking and dimension settings. Editing a contract
   number means editing the manual in the same change.

## ADR index

See [`architecture/ARCHITECTURE-INDEX.md`](architecture/ARCHITECTURE-INDEX.md) for
the status table and the relationships between records. In order:

- [ADR-001: Monorepo Structure](architecture/ADR-001-monorepo-structure.md)
- [ADR-002: Database Selection](architecture/ADR-002-database-postgresql.md)
- [ADR-003: Deployment Architecture](architecture/ADR-003-deployment-architecture.md)
- [ADR-004: LangGraph Multi-Agent Architecture](architecture/ADR-004-langgraph-multi-agent.md)
- [ADR-005: Flight Plan Pipeline](architecture/ADR-005-flight-plan-pipeline.md)
- [ADR-006: Scene/Session Split and Persistent LangGraph State](architecture/ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-007: LLM Provider Adapters](architecture/ADR-007-llm-provider-adapters.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](architecture/ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
- [ADR-009: OpenTelemetry and Postgres Trace](architecture/ADR-009-opentelemetry-and-postgres-trace.md)
