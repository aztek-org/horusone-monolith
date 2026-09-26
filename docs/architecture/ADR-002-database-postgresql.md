# ADR-002: Database Selection

**Date**: 2026-03-07  
**Status**: Accepted

## Context

The initial MVP is stateless — all session data is lost on backend restart. We need persistent storage for:
- Training sessions (who trained, when, how long)
- Voice logs (transcripts of pilot/ATC exchanges)
- Scenarios (reusable training configurations)

## Decision

**PostgreSQL 16** via **SQLAlchemy 2.x async** with **Alembic** migrations.

## Rationale

| Option | Pros | Cons |
|--------|------|------|
| PostgreSQL | Production-grade, ACID, rich queries | Requires separate service |
| SQLite | Simple, no separate service | Poor async support, no concurrent writes |
| MongoDB | Flexible schema | Unnecessary for structured aviation data |

PostgreSQL was chosen because:
- Aviation training data is highly relational (sessions → logs → scenarios)
- AsyncPG provides excellent async performance for FastAPI
- Docker Compose makes running it locally trivial
- Alembic provides safe, version-controlled schema migrations

## Consequences

- Backend requires a running PostgreSQL instance (provided by Docker Compose)
- `DATABASE_URL` must be set in `.env` for the backend to start
- All DB access goes through the **repository pattern** (`app/db/repositories/`)
- SQLAlchemy models live in `app/models/`, Pydantic schemas in `app/schemas/`
- Always create a migration with `alembic revision --autogenerate -m "description"` when changing models
- The database also carries capabilities added by later decisions: the
  **pgvector** extension and its 768-dimensional `content_chunks.embedding`
  column ([ADR-008](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)),
  the **LangGraph checkpoint tables** that persist training session state
  ([ADR-006](./ADR-006-scene-session-and-persistent-langgraph.md)), and the
  **provenance event table** backing instructor trace
  ([ADR-009](./ADR-009-opentelemetry-and-postgres-trace.md)). The choice of
  PostgreSQL is unchanged; what it now hosts is larger than this ADR originally
  described.
- All SQL in `backend/app/` is parameterised — every statement goes through
  SQLAlchemy expression binding, and the only literal `text()` calls are
  constants (`SELECT 1`, `org_id IS NULL`). This is load-bearing for telemetry,
  not just good hygiene; see
  [ADR-009](./ADR-009-opentelemetry-and-postgres-trace.md).

## References

- Related ADR: [ADR-006: Scene/Session Split and Persistent LangGraph State](./ADR-006-scene-session-and-persistent-langgraph.md)
- Related ADR: [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](./ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
- Related ADR: [ADR-009: OpenTelemetry and Postgres Trace](./ADR-009-opentelemetry-and-postgres-trace.md)
- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
