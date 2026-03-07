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
