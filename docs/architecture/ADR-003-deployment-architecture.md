# ADR-003: Deployment Architecture

**Date**: 2026-03-07  
**Status**: Accepted

## Context

Horus has a frontend (Nuxt.js) and backend (FastAPI). We need to choose where and how to deploy each.

## Decision

- **Frontend** → **Cloudflare Pages** (edge deployment, global CDN)
- **Backend** → **Private VPS** via **Docker Compose**

These are independent deployments that communicate over HTTPS/WSS.

## Frontend (Cloudflare Pages)

- Build command: `pnpm build` with `nitro.preset = 'cloudflare-pages'`
- Output: Cloudflare Workers + static assets
- Environment variables injected at build time via Cloudflare dashboard
- Key env vars: `NUXT_PUBLIC_API_URL`, `NUXT_PUBLIC_WS_URL`

## Backend (VPS + Docker Compose)

Docker Compose stack (`backend/docker-compose.yml`):
```
┌─────────────────────────────────┐
│         Private VPS              │
│                                  │
│  ┌─────────┐  ┌───────────────┐  │
│  │ postgres │  │   ollama      │  │
│  │ :5432    │  │  :11434       │  │
│  └────┬─────┘  └──────┬────────┘  │
│       │               │          │
│  ┌────┴───────────────┴───────┐  │
│  │       backend (FastAPI)    │  │
│  │          :8000             │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
         ↕ HTTPS/WSS
   Cloudflare Pages (Frontend)
```

## Communication

- REST API: `https://<vps-domain>/api/v1/`
- WebSocket: `wss://<vps-domain>/ws/voice`
- Frontend never talks directly to PostgreSQL or Ollama

## Consequences

- Backend must handle CORS for the Cloudflare Pages domain
- WebSocket must use `wss://` (TLS) in production
- VPS needs a reverse proxy (nginx/Caddy) in front of FastAPI for TLS termination
- Frontend and backend can be updated independently
