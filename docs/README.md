# Horus Documentation Index

This directory uses a single-source-of-truth documentation model to keep guides reliable and
maintainable as the platform grows.

## Canonical documents

| File | Purpose |
|------|---------|
| `docs/development.md` | Main developer guide for setup, architecture overview, testing, deployment, and troubleshooting |
| `docs/OLLAMA_SETUP.md` | Ollama deployment and configuration scenarios (local, shared, remote) |
| `docs/architecture/ADR-*.md` | Architecture Decision Records (ADRs) |

## Documentation conventions

1. Keep setup and onboarding in `docs/development.md`.
2. Keep architecture decisions in ADR files under `docs/architecture/`.
3. Prefer links to canonical docs instead of repeating long setup/status content in new files.
4. Remove temporary or one-off status docs after their relevant content is merged into canonical docs.

## ADR index

- [ADR-001: Monorepo Structure](architecture/ADR-001-monorepo-structure.md)
- [ADR-002: Database Selection](architecture/ADR-002-database-postgresql.md)
- [ADR-003: Deployment Architecture](architecture/ADR-003-deployment-architecture.md)
- [ADR-004: LangGraph Multi-Agent Architecture](architecture/ADR-004-langgraph-multi-agent.md)
- [ADR-005: Flight Plan Pipeline](architecture/ADR-005-flight-plan-pipeline.md)
