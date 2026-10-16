# Horus MVP — GitHub Copilot Custom Instructions

## Project Overview

**Horus** is an AI-Powered Aviation Training & Simulation Platform. It enables real-time ATC (Air Traffic Control) voice communication practice using local LLM inference, speech recognition, and text-to-speech.

- **Domain**: Aviation / Flight Training / ATC Simulation
- **Frontend** → Deployed to **Cloudflare Pages** (Nuxt 4 + Vue 3)
- **Backend** → Deployed to **Private VPS** via Docker Compose (FastAPI + Python)
- **Realtime** → Rust + Go microservices for WebSocket and event processing
- **Auth** → Keycloak (OIDC) for authentication and multi-tenant authorization
- These layers are **independently deployed** — never mix their environments or configs.

---

## Architecture Layers

```
Edge Layer       → Traefik (reverse proxy, TLS, rate limiting)
                 → Keycloak (OIDC authentication, RBAC, multi-tenancy)

Realtime Layer   → Rust (WebSocket gateway, audio routing)
                 → Go (event processing, telemetry collection, gRPC)

Control Layer    → Python/FastAPI (business logic, LangGraph, scenario engine)
                 → LangGraph (stateful ATC agent orchestration)
                 → Whisper STT, Coqui TTS, Ollama LLM

Data Layer       → PostgreSQL (primary relational store)
                 → Redis (caching, session state, pub/sub)
                 → Qdrant (vector search for RAG)

Frontend         → Nuxt 4 / Vue 3 / TailwindCSS / Cloudflare Pages
```

---

## Business Model

- **Admin**: Platform-wide management
- **Organization**: Flight school / airline — has administrators, instructors, students (seats)
- **User (seat)**: Pilot trainee, can exist standalone or within an organization
- Users can register independently and later be invited to an organization
- **Each organization sees only its own data** — this is the #1 security boundary
- Sessions generate tracking data for feedback & analytics

---

## Repository Structure

```
horus-mvp/
├── backend/                    # FastAPI Python backend (VPS)
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Pydantic settings (env-based)
│   │   ├── api/routes/         # Route handlers
│   │   ├── core/               # Audio pipeline + WebSocket manager
│   │   ├── db/                 # SQLAlchemy async session + repositories
│   │   ├── middleware/         # Auth (Keycloak JWT), CORS, timing
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   └── services/           # STT, TTS, LLM (LangGraph), audio effects
│   ├── tests/
│   ├── alembic/                # Database migrations
│   ├── docker/                 # Dockerfile + docker-compose.yml
│   └── pyproject.toml          # uv package manager config
│
├── realtime/                   # Rust + Go real-time microservices
│   ├── ws-gateway/             # Rust WebSocket gateway (Axum/Tokio)
│   ├── event-processor/        # Go event processing service
│   └── telemetry/              # Go telemetry collector
│
├── frontend/                   # Nuxt 4 frontend (Cloudflare Pages)
│   ├── app/
│   │   ├── pages/              # Auto-routed pages
│   │   ├── components/
│   │   │   ├── ui/             # H-prefixed design system components
│   │   │   ├── shared/         # Layout components
│   │   │   ├── scenario-architect/
│   │   │   └── mission-hub/
│   │   ├── composables/        # Vue Composition API state + useAuth
│   │   └── layouts/
│   ├── nuxt.config.ts
│   ├── tailwind.config.ts
│   └── apps/*/wrangler.toml   # Cloudflare Pages config (per app)
│
├── docs/
│   ├── architecture/           # Architecture Decision Records (ADRs)
│   └── development.md          # Single onboarding guide
│
└── .github/
    ├── copilot-instructions.md # This file
    ├── CODEOWNERS
    ├── agents/                 # Copilot Fleet agent definitions
    │   ├── database-expert.agent.md
    │   ├── docker-devops.agent.md
    │   ├── document-agent.agent.md
    │   ├── golang-expert.agent.md
    │   ├── keycloak-expert.agent.md
    │   ├── llm-expert.agent.md
    │   ├── nuxt-expert.agent.md
    │   ├── python-fastapi-expert.agent.md
    │   ├── rust-expert.agent.md
    │   └── security-expert.agent.md
    └── skills/                 # Skill files for common tasks
        ├── add-api-endpoint/
        ├── add-db-model/
        ├── add-go-service/
        ├── add-rust-service/
        ├── add-vue-component/
        ├── aviation-domain/
        ├── debug-audio-pipeline/
        ├── keycloak-integration/
        ├── security-review/
        └── write-adr/
```

---

## Backend Conventions (Python / FastAPI)

### Language & Tooling
- **Python 3.10–3.11** (must stay in range per pyproject.toml)
- **Package manager**: `uv` — use `uv pip install` not `pip install`
- **Linter**: `ruff` — run `ruff check app/` and `ruff format app/`
- **Type checker**: `mypy` — strict mode, all functions need type hints
- **Tests**: `pytest` with `pytest-asyncio` — run `pytest tests/ -v`

### Code Style
- All functions and methods **must have type annotations**
- Docstrings use Google style (Args/Returns/Raises)
- Line length: 100 characters (ruff enforces this)
- Imports: stdlib → third-party → local (ruff sorts automatically)
- Use `async/await` throughout — this is an async FastAPI app

### Architecture Patterns
- **Routes** (`app/api/routes/`): Thin — validate input, call service, return response
- **Services** (`app/services/`): Business logic per domain (STT, TTS, LLM, audio_effects)
- **Repositories** (`app/db/repositories/`): All DB access goes through repository classes
- **Models** (`app/models/`): SQLAlchemy ORM models with `Base` from `app/db/base.py`
- **Schemas** (`app/schemas/`): Pydantic models for API input/output — separate from ORM models
- **Config** (`app/config.py`): All settings via `pydantic-settings`, loaded from `.env`

### Database
- SQLAlchemy 2.x async — always use `AsyncSession` + `async with`
- Repositories inject `AsyncSession` via FastAPI's `Depends(get_db_session)`
- Migrations via Alembic — always create a migration after changing models
- Models inherit from `Base` in `app/db/base.py`

### API Versioning
- All REST routes are prefixed `/api/v1/`
- WebSocket stays at `/ws/voice` (no version prefix — clients may be hardcoded)
- Health endpoints stay at `/health` and `/health/ready`

### Error Handling
- Use `HTTPException` for API errors with meaningful status codes
- Log errors with `logger = logging.getLogger(__name__)` at module level
- Never swallow exceptions silently

---

## Frontend Conventions (TypeScript / Nuxt 4 / Vue 3)

### Language & Tooling
- **TypeScript** everywhere — no `any` unless absolutely unavoidable (triggers ESLint warning)
- **Package manager**: `pnpm` — use `pnpm add` not `npm install`
- **Linter**: ESLint with `@nuxt/eslint` — run `pnpm lint`
- **Formatter**: Prettier — run `pnpm format`
- **Tests**: Vitest with `@nuxt/test-utils` — run `pnpm test`

### Component Conventions
- UI design system components use the `H` prefix: `HButton`, `HCard`, `HBadge`, etc.
- Components go in `app/components/ui/` (design system), `shared/` (layout), or feature dirs
- Use Vue 3 `<script setup lang="ts">` syntax — never Options API
- Props must have explicit TypeScript types using `defineProps<{...}>()`
- Emit events explicitly with `defineEmits<{...}>()`

### State Management
- Use Nuxt composables (`useXxx.ts`) in `app/composables/` — no Pinia for now
- Composables use Vue `ref`/`computed`/`watch` from the Composition API
- Shared state is exported from composables as `ref` objects

### Environment & API URLs
- Never hardcode `localhost` or backend URLs in components/composables
- Use `useRuntimeConfig().public.apiUrl` and `useRuntimeConfig().public.wsUrl`
- These are set via `runtimeConfig.public` in `nuxt.config.ts` and injected from env at build time

### Styling
- TailwindCSS only — no inline styles, no separate CSS files per component (except `main.css`)
- Design tokens are in `tailwind.config.ts` (colors: `horus-*`, `atc-*`)
- Dark theme by default — all colors must have sufficient contrast on dark backgrounds

---

## Domain Context (Aviation / ATC)

### Key Concepts
- **ATC**: Air Traffic Control — ground-based controllers guiding aircraft
- **Pilot/Controller communication** follows strict ICAO phraseology
- **ICAO phraseology**: Standardized radio communication language ("Roger", "Wilco", "Cleared for takeoff", etc.)
- **Callsign**: Aircraft identifier used in radio calls (e.g., "Delta 123", "N12345")
- **ATIS**: Automatic Terminal Information Service — recorded weather/airport info
- **ILS**: Instrument Landing System — precision approach guidance
- **VFR/IFR**: Visual/Instrument Flight Rules — different operating conditions

### Scenario Types
- **Ground** operations: Pushback, taxi, runway crossings
- **Departure**: Takeoff clearances, initial climb, SID (Standard Instrument Departure)
- **Enroute**: Cruise altitude changes, handoffs between sectors
- **Approach**: STAR (Standard Arrival), approach clearances, ILS intercept
- **Landing**: Landing clearance, rollout, turnoff, taxi to gate

### Common ICAO Phrases
- "Cleared for takeoff [runway]"
- "Descend and maintain flight level [xxx]"
- "Contact [facility] on [frequency]"
- "Traffic [clock position], [distance], [type aircraft]"
- "Wind [direction] at [speed], altimeter [setting]"
- "Squawk [code]" (transponder code assignment)

---

## Audio Pipeline (Core Feature)

The voice communication pipeline flows: **Microphone → WebSocket → STT → LLM → TTS → Radio Effects → WebSocket → Speaker**

```
Client captures audio (WebM/Opus)
  ↓ WebSocket binary message
Backend receives binary audio
  ↓ Whisper STT
Text transcript of pilot speech
  ↓ LangGraph + Ollama LLM
ATC response text (ICAO phraseology)
  ↓ Coqui TTS (or gTTS fallback)
Audio WAV bytes
  ↓ scipy band-pass filter + noise
Radio-effect processed audio
  ↓ WebSocket binary message
Client plays audio
```

When debugging this pipeline, check each stage in sequence. Use the `/health/ready` endpoint to verify all services are up.

---

## Testing Philosophy

- **Unit tests** (`tests/unit/`): Test a single function/class in isolation. Mock all I/O.
- **Integration tests** (`tests/integration/`): Test full HTTP request/response cycle using `TestClient`.
- **Never** call real Ollama, Whisper, or TTS services in tests — always mock.
- Test files mirror `app/` structure: `app/services/stt/whisper_service.py` → `tests/unit/services/stt/test_whisper_service.py`
- All test functions start with `test_`; all test classes start with `Test`

---

## Running the Project Locally

```bash
# Backend (VPS/local)
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
# Requires Ollama running: ollama serve
uvicorn app.main:app --reload --port 8000

# Frontend (Cloudflare Pages / local)
cd frontend
pnpm install
pnpm dev   # http://localhost:3000

# Tests
cd backend && pytest tests/ -v
cd frontend && pnpm test
```

---

## Realtime Layer (Rust / Go)

### Rust Services
- **WebSocket Gateway** (`realtime/ws-gateway/`): Client-facing WebSocket connections, binary audio routing
- Stack: Tokio, Axum 0.7+, serde, tokio-tungstenite
- Linting: `cargo clippy -- -W clippy::pedantic`, `cargo fmt --check`
- Testing: `cargo test`, `#[tokio::test]` for async

### Go Services
- **Event Processor** (`realtime/event-processor/`): Training event processing from Redis Streams
- **Telemetry** (`realtime/telemetry/`): High-frequency flight data collection
- Stack: Go 1.22+, chi, pgx, go-redis, slog
- Linting: `golangci-lint run ./...`
- Testing: `go test -v -race ./...`

### Inter-Service Communication
- Rust ↔ Python: Redis Streams / Pub-Sub for audio pipeline
- Go ↔ Python: gRPC for typed RPC
- All services expose `/health` endpoint

---

## Authentication & Authorization (Keycloak)

### Stack
- **Keycloak 24.x+** (Quarkus) behind Traefik at `auth.horusone.app`
- **OIDC + PKCE** for frontend SPA (no client secret)
- **JWT RS256** tokens validated by backend middleware

### Roles
- `platform-admin` — Full platform access
- `org-admin` — Organization administrator
- `instructor` — Create scenarios, view student progress
- `student` — Seat holder, access assigned training

### Multi-Tenancy
- JWT includes `organization_id` custom claim
- Backend middleware extracts `org_id` → all queries filter by it
- PostgreSQL RLS as defense-in-depth
- Frontend uses `useAuth()` composable for OIDC flow

---

## Copilot Fleet — Agent Reference

| Agent | Focus |
|-------|-------|
| `database-expert` | PostgreSQL, Redis, Qdrant, schema design, migrations |
| `docker-devops` | Docker, Traefik, CI/CD, deployment, infrastructure |
| `document-agent` | ADRs, documentation, README, code comments |
| `golang-expert` | Go real-time services, event processing, gRPC |
| `keycloak-expert` | OIDC, auth/authz, multi-tenancy, realm config |
| `llm-expert` | LangGraph, Ollama, prompt engineering, RAG, Qdrant |
| `nuxt-expert` | Nuxt 4, Vue 3, TailwindCSS, frontend components |
| `python-fastapi-expert` | FastAPI, async Python, SQLAlchemy, backend API |
| `rust-expert` | Rust real-time services, WebSocket, Tokio/Axum |
| `security-expert` | OWASP, data isolation, RBAC, dependency scanning |
