# ADR-001: Monorepo Structure

**Date**: 2026-03-07  
**Status**: Accepted

## Context

Horus MVP contains a Python FastAPI backend and a Nuxt.js frontend. We need to decide how to organize them — separate repositories or a single monorepo.

## Decision

Keep both in a **single monorepo** with independently deployable units.

The root level contains shared tooling (`.editorconfig`, `package.json` convenience scripts, `README.md`). Each subdirectory (`backend/`, `frontend/`) is fully self-contained with its own dependencies, configs, and deployment targets.

## Consequences

**Positive:**
- Single `git clone` to get the full system
- Easier cross-cutting changes (e.g., updating shared type contracts)
- Unified issue tracking and PR review
- Copilot can understand the full system from one checkout

**Negative:**
- Requires discipline to not couple frontend and backend code
- CI/CD must be smart about only building what changed

## Deployment Targets

- **Frontend** → Cloudflare Pages (edge, global CDN)
- **Backend** → Private VPS via Docker Compose

These are **never co-deployed** in the same container or process.

## References

- Index: [ARCHITECTURE-INDEX.md](./ARCHITECTURE-INDEX.md)
