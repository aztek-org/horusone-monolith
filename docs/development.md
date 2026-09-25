# Horus — Development Guide

Complete guide for setting up and working on the Horus Aviation Training Platform.

For documentation structure and canonical sources, see [`docs/README.md`](README.md).

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10–3.11 | Backend runtime |
| Node.js | 22+ | Frontend build |
| pnpm | 9+ | Frontend package manager |
| uv | latest | Python package manager |
| Docker + Compose | latest | Infrastructure (PostgreSQL, Redis, Ollama, Keycloak) |
| Ollama | latest | Local LLM inference |
| (Optional) psql | any | PostgreSQL client for manual queries |

---

## Quick Start (5 minutes)

```bash
# 1. Clone and run setup
git clone <repo-url>
cd horus-mvp
./setup.sh                    # checks prereqs, installs deps

# 2. Start infrastructure
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama

# 3. Sync deps, run migrations, seed data
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed

# 4. Pull Ollama model (first time — takes a few minutes)
ollama pull llama3.2:3b

# 5. Start the backend
./run_backend.sh

# 6. Start the frontend (new terminal)
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:3002](http://localhost:3002) to use the Hangar login gateway.

> **💡 Tip:** Set `AUTH_ENABLED=false` in `backend/.env` to skip Keycloak and get a dev user automatically. This is the easiest way to develop locally.

---

## Architecture Overview

Horus uses a 5-layer architecture:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Edge** | Traefik + Keycloak 24 | Reverse proxy, TLS termination, identity/auth |
| **Realtime** | *(Planned)* Rust WebSocket gateway + Go event processor | Low-latency voice streaming |
| **Control** | Python/FastAPI + LangGraph multi-agent AI | API, business logic, ATC AI pipeline |
| **Data** | PostgreSQL 16 + Redis 7 + *(Planned)* Qdrant | Persistence, caching, vector search |
| **Frontend** | Nuxt 4 + Vue 3 + TailwindCSS | SPA on Cloudflare Pages |

### LangGraph Multi-Agent System

Horus composes three `StateGraph` sub-graphs behind a single Session module
(`TrainingSessionModule`) with 9 specialized agents:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TrainingSessionModule                            │
├─────────────────┬──────────────────────────┬────────────────────────────┤
│  Validation     │  Live Session            │  Scoring                   │
│  Graph          │  Graph                   │  Graph                     │
│                 │                          │                            │
│  ┌───────────┐  │  ┌─────────────────┐     │  ┌──────────────┐         │
│  │Gatekeeper │  │  │Understand Input │     │  │Student Tier  │         │
│  │Weather    │  │  │Emergency Handler│     │  │Gamification  │         │
│  │Fuel       │  │  │ATC Response(LLM)│     │  │Report Gen    │         │
│  │Route      │  │  │Evaluate Exchange│     │  └──────────────┘         │
│  │Airspace   │  │  └─────────────────┘     │                           │
│  │Performance│  │                          │                            │
│  └───────────┘  │                          │                            │
└─────────────────┴──────────────────────────┴────────────────────────────┘
```

- **Validation graph** — pre-flight: Gatekeeper → Weather → Fuel → Route → Airspace → Performance
- **Live session graph** — per-exchange: classify input → emergency or LLM ATC → evaluate
- **Scoring graph** — post-flight: student evaluation → badge awards → report generation

`HorusOrchestrator`, which used to compose these, was retired; `ATCAgent` remains
as a thin adapter for the `AudioPipeline` interface. See
[ADR-006](architecture/ADR-006-scene-session-and-persistent-langgraph.md).

**Human-in-the-loop (HITL) is built and deliberately switched off.** The live
graph can be compiled to pause before the ATC response and before the emergency
handler, and `TrainingSessionModule.await_instructor()` can release a held
exchange with the instructor's own words or with the graph's — with the pending
state checkpointed, so a review survives a restart. But no config field sets
`interrupt_before_response`, no route calls `await_instructor`, and the frontend
renders no pending state, so **no deployment has instructor override available**.
Turning it on needs all three; tracked in
[#3](https://github.com/martinsgmx/horusone-mvp/issues/3). Don't debug HITL as if
it were live: if you are reading this expecting to override a response, the flag
is `False` and the path is unreachable.

📖 Full details: [ADR-004: LangGraph Multi-Agent Architecture](architecture/ADR-004-langgraph-multi-agent.md)

### Audio Pipeline

```
Microphone → WebSocket → Whisper STT → LangGraph/Ollama LLM → TTS → Radio Effects → WebSocket → Speaker
```

See [`.github/skills/debug-audio-pipeline/SKILL.md`](../.github/skills/debug-audio-pipeline/SKILL.md) for a step-by-step debug checklist.

---

## Project Structure

```
horus-mvp/
├── backend/                        # FastAPI Python backend (VPS)
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Pydantic settings (env-based)
│   │   ├── api/
│   │   │   ├── routes/             # Core routes (health, voice WebSocket)
│   │   │   └── v1/                 # Versioned API routes
│   │   │       ├── admin.py        # Organization + user management
│   │   │       ├── analytics.py    # Leaderboard + overview
│   │   │       ├── assessments.py  # Knowledge assessments + auto-grading
│   │   │       ├── auth.py         # Authentication (session, logout, me)
│   │   │       ├── content.py      # Knowledge base articles + search
│   │   │       ├── flight_plans.py # Flight plan CRUD + validation + OCR
│   │   │       ├── gamification.py # Badges + leaderboard
│   │   │       ├── instructors.py  # Instructor profiles
│   │   │       ├── modules.py      # Training modules
│   │   │       ├── preferences.py  # User preferences
│   │   │       ├── scenarios.py    # Scenario CRUD
│   │   │       ├── sessions.py     # Training session CRUD
│   │   │       ├── stats.py        # Student statistics + transcripts
│   │   │       └── waypoints.py    # Waypoint search + flight track
│   │   ├── core/                   # Audio pipeline + WebSocket manager
│   │   ├── db/                     # SQLAlchemy async session + repositories
│   │   ├── models/                 # ORM models (User, Organization, Seat, Scenario, etc.)
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   └── services/               # STT, TTS, LLM, audio effects
│   │       └── llm/                # LangGraph multi-agent system
│   │           ├── atc_agent.py      # ATCAgent: adapter over the live-session graph
│   │           ├── state.py         # HorusState shared TypedDict
│   │           ├── agents/          # 9 specialist agents
│   │           ├── graphs/          # 3 compiled sub-graphs (builder functions)
│   │           ├── scenes/          # Scene registry + packaged default Scene
│   │           ├── tools/           # Weather, airspace, calculation tools
│   │           └── prompts.py       # ATC prompt templates
│   │       ├── training_sessions/  # Session module: lifecycle, store, events, trace
│   │       ├── knowledge/          # Ingest, chunking, pgvector + fake retrievers
│   │       └── observability/      # OpenTelemetry wiring + privacy scrubber
│   ├── tests/                      # pytest test suite (unit/ + integration/)
│   ├── alembic/                    # Database migrations
│   ├── scripts/                    # seed.py, deploy.sh, backup.sh, restore.sh,
│   │                               # prune_session_events.py (ADR-009 retention cron)
│   ├── docker/                     # Dockerfile + keycloak-import/
│   ├── docker-compose.yml          # Base service definitions
│   ├── docker-compose.dev.yml      # Dev overrides (exposed ports, hot reload)
│   ├── docker-compose.prod.yml     # Prod overrides (TLS, resource limits, GPU)
│   ├── run_backend.sh              # Dev convenience script
│   └── pyproject.toml              # uv package manager config
│
├── frontend/                       # Nuxt 4 frontend (Cloudflare Pages)
│   ├── app/
│   │   ├── pages/                  # Auto-routed pages (25+ routes)
│   │   ├── components/
│   │   │   ├── ui/                 # H-prefixed design system (HButton, HCard, etc.)
│   │   │   ├── shared/             # Layout components
│   │   │   ├── scenario-architect/ # Scenario configuration
│   │   │   └── mission-hub/        # Live mission components
│   │   ├── composables/            # Vue Composition API state
│   │   └── layouts/                # Page layouts
│   ├── nuxt.config.ts
│   ├── tailwind.config.ts
│   └── wrangler.toml               # Cloudflare Pages config
│
├── docs/
│   ├── README.md                   # Documentation index (canonical doc map)
│   ├── development.md              # Main developer guide
│   ├── OLLAMA_SETUP.md             # LLM configuration guide
│   ├── knowledge/                  # Operator manuals for the knowledge path
│   │   ├── INGEST.md               # Ingest formats, chunking, dimensions, tenancy
│   │   └── RETRIEVAL.md            # pgvector retrieval, HNSW, hybrid search
│   └── architecture/               # Architecture Decision Records (ADRs)
│       ├── ARCHITECTURE-INDEX.md   # Decision -> ADR -> status
│       ├── ADR-001-monorepo-structure.md
│       ├── ADR-002-database-postgresql.md
│       ├── ADR-003-deployment-architecture.md
│       ├── ADR-004-langgraph-multi-agent.md
│       ├── ADR-005-flight-plan-pipeline.md
│       ├── ADR-006-scene-session-and-persistent-langgraph.md
│       ├── ADR-007-llm-provider-adapters.md
│       ├── ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md
│       └── ADR-009-opentelemetry-and-postgres-trace.md
│
└── setup.sh                        # One-time project setup script
```

---

## Backend Setup (Detailed)

### Environment Variables

Copy the example env file and customize for local development:

```bash
cd backend
cp .env.example .env
```

Key variables to set for local dev:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://horus:horus@localhost:5432/horus_db` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_LLM_MODEL` | `llama3.2:3b` | LLM model name for ATC responses |
| `AUTH_ENABLED` | `true` | **Set to `false` to skip Keycloak locally** |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3000` | Allowed frontend origins |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small/medium/large) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

See the [Environment Variable Reference](#environment-variable-reference) at the end of this document for the full list.

### Database

PostgreSQL 16 runs via Docker with the dev compose overlay exposing port 5432.

```bash
# Start PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres

# Run all migrations
cd backend
uv run alembic upgrade head

# Create a new migration after changing models
uv run alembic revision --autogenerate -m "describe_your_change"

# Check current migration state
uv run alembic current

# Downgrade one step
uv run alembic downgrade -1
```

**Database tables:** `users`, `organizations`, `seats`, `scenarios`, `training_sessions`, `voice_logs`, `training_modules`, `student_stats`, `content_categories`, `content_articles`, `waypoints`, `flight_plans`, `flight_track_points`, `flight_insights`, `instructor_profiles`, `badges`, `user_badges`, `leaderboard_snapshots`, `assessments`, `assessment_questions`, `assessment_results`, `user_preferences`

**Seed data** (idempotent — safe to run repeatedly):

```bash
uv run python -m scripts.seed              # insert seed data (skips existing rows)
uv run python -m scripts.seed --reset      # truncate all tables, then re-seed
```

The seed script creates a sample organization (`skybridge.aero`), users with different roles (admin, instructor, student), seats, scenarios, training sessions, and voice logs.

### Authentication

Horus uses **Keycloak 24 (Quarkus)** for identity management. The Docker setup auto-imports the `horus` realm from `docker/keycloak-import/horus-realm.json`.

#### Local dev WITHOUT Keycloak (recommended for most development)

Set in `backend/.env`:

```env
AUTH_ENABLED=false
```

All requests will return a dev user — no login required.

#### Local dev WITH Keycloak

```bash
# Start Keycloak alongside other services
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama keycloak
```

- **Keycloak admin console**: http://localhost:8180 (admin / admin)
- The `horus` realm is auto-imported on first start
- Frontend uses **OIDC PKCE flow** (no client secret)
- Backend validates **RS256 JWT tokens** with JWKS endpoint caching

### Running the Backend

```bash
cd backend

# Option 1: convenience script (loads .env automatically)
./run_backend.sh

# Option 2: manual
uv run --env-file .env uvicorn app.main:app --reload
```

The API server starts at http://localhost:8000.

### API Endpoints

#### Core

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check (verifies all services) |
| WebSocket | `/ws/voice` | Real-time voice communication (JWT required, 2MB chunk limit, 10MB total payload limit) |

#### Authentication (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/session` | Create auth session |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Current user profile |

#### Scenarios & Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/scenarios` | List / create scenarios |
| GET | `/api/v1/scenarios/{id}` | Get scenario details |
| GET/POST | `/api/v1/sessions` | List / create training sessions (`GET` supports `status`, `scenario_id`, `started_after`, `started_before`) |
| GET | `/api/v1/sessions/{id}` | Get training session details |
| GET | `/api/v1/sessions/{id}/events` | Get ordered session lifecycle audit events |
| GET | `/api/v1/sessions/{id}/replay` | Get replay payload (track, insights, voice logs, scoring) |
| POST | `/api/v1/sessions/{id}/complete` | Complete active session (idempotent) and return replay path |

#### Training Modules (`/api/v1/modules`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/modules` | List training modules visible to caller scope (org + shared for org users) |
| POST | `/modules` | Create training module (org-scoped for non-platform users) |
| GET/PUT/DELETE | `/modules/{id}` | Read/update/delete module with org-scope authorization |
| POST | `/modules/{id}/scenarios` | Link scenario to module (scope validated) |
| DELETE | `/modules/{id}/scenarios/{scenario_id}` | Unlink scenario from module (scope validated) |

#### Student Statistics (`/api/v1/stats`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats/me` | Current user's stats (flight hours, scenarios completed, etc.) |
| GET | `/stats/me/flight-hours` | Detailed flight hours breakdown |
| GET | `/stats/me/maneuvers` | Maneuvers practiced summary (supports optional `type` filter) |
| GET | `/stats/me/assessments` | Assessment results history |
| GET | `/stats/me/transcript/{session_id}` | Download session transcript |
| GET | `/stats/{user_id}` | Stats for a specific user (instructor/admin) |

#### Content / Knowledge Base (`/api/v1/content`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/content/categories` | List content categories |
| GET | `/content/categories/{slug}` | Get category with articles |
| GET | `/content/articles/{slug}` | Get article by slug |
| POST | `/content/articles` | Create article (instructor/admin) |
| PUT | `/content/articles/{id}` | Update article |
| GET | `/content/search` | Full-text search across articles |

#### Waypoints (`/api/v1/waypoints`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/waypoints/` | Search waypoints (by name, type, bounding box) |
| POST | `/waypoints/` | Create custom waypoint |
| GET | `/waypoints/scenarios/{id}/waypoints` | Waypoints for a scenario |
| POST | `/waypoints/scenarios/{id}/waypoints` | Add waypoints to scenario |
| GET | `/waypoints/sessions/{id}/track` | Recorded flight track for session |
| GET | `/waypoints/sessions/{id}/insights` | AI-generated flight insights |

#### Flight Plans (`/api/v1/flight-plans`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/flight-plans/` | List user's flight plans |
| POST | `/flight-plans/` | Create from structured form data |
| POST | `/flight-plans/from-text` | Create from free-form text |
| POST | `/flight-plans/from-image` | Create from uploaded image (OCR) |
| GET | `/flight-plans/{id}` | Get flight plan details |
| PUT | `/flight-plans/{id}` | Update a draft flight plan |
| POST | `/flight-plans/{id}/validate` | Run AI validation pipeline |
| POST | `/flight-plans/{id}/activate` | Activate for live session |

See [ADR-005: Flight Plan Pipeline](architecture/ADR-005-flight-plan-pipeline.md) for details.

#### Instructors (`/api/v1/instructors`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/instructors/me/profile` | Current instructor's profile |
| PUT | `/instructors/me/profile` | Update own profile |
| GET | `/instructors/{user_id}/profile` | Get instructor profile |
| GET | `/instructors/` | List all instructors |

#### Gamification (`/api/v1/gamification`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/gamification/badges` | List all available badges |
| POST | `/gamification/badges` | Create an organization-scoped badge definition |
| GET | `/gamification/me/badges` | Current user's earned badges |
| GET | `/gamification/leaderboard` | Leaderboard snapshot (daily/weekly/monthly) |
| POST | `/gamification/check` | Trigger badge evaluation for current session |

#### Assessments (`/api/v1/assessments`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/assessments/` | List available assessments |
| GET | `/assessments/me/results` | Current user's assessment results |
| GET | `/assessments/{id}` | Get assessment details + questions |
| POST | `/assessments/` | Create assessment (instructor/admin) |
| POST | `/assessments/{id}/submit` | Submit answers for auto-grading |

#### Analytics (`/api/v1/analytics`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/leaderboard` | Global leaderboard entries |
| GET | `/analytics/overview` | Platform-wide analytics overview |
| GET | `/analytics/platform-org-leaderboard` | Platform org ranking by completed sessions |

#### User Preferences (`/api/v1/users/me/preferences`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me/preferences` | Get user preferences |
| PUT | `/users/me/preferences` | Replace user preferences |
| PATCH | `/users/me/preferences/{section}` | Update a single section |

#### Admin (`/api/v1/admin`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/admin/organizations/` | List / create organizations |
| GET/PUT/DELETE | `/admin/organizations/{id}` | Organization CRUD |
| GET/POST | `/admin/organizations/{id}/seats` | Manage seats in org |
| PUT/DELETE | `/admin/seats/{id}` | Update / remove a seat |
| GET | `/admin/users/` | List all users |
| GET/PUT | `/admin/users/{id}` | User detail / update |
| GET | `/admin/stats` | Platform-wide admin statistics |

### Adding Endpoints, Models, and Security Reviews

- **New API endpoint**: See [`.github/skills/add-api-endpoint/SKILL.md`](../.github/skills/add-api-endpoint/SKILL.md)
- **New database model**: See [`.github/skills/add-db-model/SKILL.md`](../.github/skills/add-db-model/SKILL.md)
- **OWASP security review**: See [`.github/skills/owasp-security/SKILL.md`](../.github/skills/owasp-security/SKILL.md)

---

## Frontend Setup (Detailed)

### Installation

```bash
cd frontend
pnpm install
# run all apps
pnpm dev

# or run individually
pnpm dev:squawk   # http://localhost:3000
pnpm dev:tower    # http://localhost:3001
pnpm dev:hangar   # http://localhost:3002
```

### Environment

Runtime config is set via `nuxt.config.ts` with sensible localhost defaults. No `.env` file needed for local dev unless you want to override:

- `NUXT_PUBLIC_API_URL` → defaults to `http://localhost:8000`
- `NUXT_PUBLIC_WS_URL` → defaults to `ws://localhost:8000/ws/voice`
- `NUXT_PUBLIC_KEYCLOAK_URL` → defaults to `http://localhost:8180`
- `NUXT_PUBLIC_KEYCLOAK_REALM` → defaults to `horus`
- `NUXT_PUBLIC_KEYCLOAK_CLIENT_ID` → defaults to `horus-web`
- `NUXT_PUBLIC_HANGAR_URL` → defaults to `http://localhost:3002`
- `NUXT_PUBLIC_TOWER_URL` → defaults to `http://localhost:3001`
- `NUXT_PUBLIC_SQUAWK_URL` → defaults to `http://localhost:3000`
- `NUXT_PUBLIC_AUTH_GATEWAY_URL` → defaults to Hangar URL

For production, set `NUXT_PUBLIC_*` env vars in the Cloudflare Pages dashboard.

### App Domains and Auth Flow

| App | Local URL | Domain Scope | Current State |
|-----|-----------|--------------|---------------|
| Hangar | `http://localhost:3002` | Student / seat experience | Main login gateway + full pilot flow pages + server-filtered range-aware performance analytics + live trend chart + dynamic streak insights + session replay audit timeline + transcript export (TXT/JSON) + stats transcript quick-download actions + assessment result exports + personal settings workspace |
| Tower | `http://localhost:3001` | Organization admin / instructor | Org operations dashboard with session visibility, billing profile controls, scenario studio, training plan module studio, badge studio, org-admin seat management, and app settings page |
| Squawk | `http://localhost:3000` | Platform admin | Platform dashboard with org oversight, billing management actions, user directory controls, and app settings page |

Role-based redirect after callback:
- `platform-admin` → Squawk
- `org-admin` / `instructor` → Tower
- `student` (fallback authenticated user) → Hangar

Route ownership enforcement:
- Hangar no longer hosts legacy admin/instructor dashboards; `/admin/*` and `/instructor/*` paths in Hangar redirect to the role-owned app dashboard.

Tower behavior:
- `org-admin`: can view org metrics, progress analytics/leaderboard, invite seats, update seat roles, manage billing profile, create org scenarios with plan templates, author training plan modules, create org-scoped custom badges, and deactivate seats
- `instructor`: operations view with session/billing visibility, progress analytics, scenario creation, plan authoring, and badge authoring capabilities

Squawk behavior:
- `platform-admin`: can view global stats, organization progress leaderboard, create/deactivate organizations, update org seat limits, manage org billing profiles, and enable/disable user accounts

### Design System

H-prefixed components live in `app/components/ui/`:

`HButton` · `HCard` · `HBadge` · `HSlider` · `HProgress` · `HCheckbox` · `HChecklistItem` · `HDropdown` · `HDataPanel` · `HSection` · `HStatusIndicator` · `HStatusPill` · `HLogEntry` · `HRadioGroup` · `HButtonGroup`

- Dark theme by default with `horus-*` and `atc-*` color tokens in `tailwind.config.ts`
- See [`.github/skills/add-vue-component/SKILL.md`](../.github/skills/add-vue-component/SKILL.md) for creating new components

---

## Docker Setup

### Development (infra in Docker, code runs locally)

```bash
cd backend

# Core infrastructure only
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama

# With Keycloak (optional)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama keycloak
```

**Exposed ports in dev:**

| Service | Port | URL |
|---------|------|-----|
| PostgreSQL | 5432 | `postgresql://horus:horus@localhost:5432/horus_db` |
| Redis | 6379 | `redis://localhost:6379/0` |
| Ollama | 11434 | `http://localhost:11434` |
| Keycloak | 8180 | `http://localhost:8180` |

### Full Stack (everything in Docker)

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Access via: `api.localhost` (backend), `auth.localhost` (Keycloak), `localhost:8081` (Traefik dashboard)

### Production

```bash
cd backend
cp .env.prod.example .env.prod    # edit with real values
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d
```

Or use the deploy script: `./scripts/deploy.sh --full`

Production features:
- Traefik handles TLS via Let's Encrypt (ACME)
- No ports exposed directly — all traffic routed through Traefik
- GPU reservations for Ollama (NVIDIA)
- Resource limits on backend (2 CPU, 2GB RAM) and PostgreSQL (1 CPU, 1GB RAM)
- Redis password-protected

---

## Testing

### Backend

```bash
cd backend

uv run pytest tests/ -v                    # all tests
uv run pytest tests/unit/ -v               # unit only
uv run pytest tests/integration/ -v        # integration only
uv run pytest tests/ --cov=app             # with coverage

uv run ruff check app/                     # lint
uv run ruff check app/ --fix               # auto-fix lint issues
uv run ruff format app/                    # format
uv run mypy app/                           # type check

uv sync --extra otel                       # install the optional OTLP exporter
uv run pytest tests/unit/test_telemetry.py # the OTLP happy path is skipped without it
```

**Testing rules:**
- Unit tests (`tests/unit/`) — test a single function/class, mock all I/O
- Integration tests (`tests/integration/`) — test full HTTP request/response with `TestClient`
- Never call real Ollama, Whisper, or TTS in tests — always mock
- Test files mirror `app/` structure: `app/services/stt/whisper_service.py` → `tests/unit/services/stt/test_whisper_service.py`

### Frontend

```bash
cd frontend

pnpm test                           # run once
pnpm test:watch                     # watch mode
pnpm lint                           # ESLint
pnpm lint:fix                       # auto-fix ESLint issues
pnpm format                         # Prettier
```

---

## Deployment

### Backend (VPS via Docker)

- Uses `docker-compose.prod.yml` overlay with Traefik for TLS
- **Deploy**: `./scripts/deploy.sh` (rolling update) or `./scripts/deploy.sh --full` (full restart)
- **Backup**: `./scripts/backup.sh` (7-day retention)
- **Restore**: `./scripts/restore.sh <backup-file>`

### Frontend (Cloudflare Pages)

1. Connect the GitHub repo to Cloudflare Pages
2. Build settings:
   - **Build command**: `cd frontend && pnpm install && pnpm build`
   - **Output directory**: `frontend/.output/public`
3. Set environment variables in the Cloudflare dashboard:
   - `CF_PAGES=1`
   - `NUXT_PUBLIC_API_URL=https://api.yourdomain.com`
   - `NUXT_PUBLIC_WS_URL=wss://api.yourdomain.com/ws/voice`
4. `wrangler.toml` has production and preview environment configs

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `uv run python -m scripts.seed` hangs | PostgreSQL not running | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres` |
| `relation "users" does not exist` | Migrations not run | `uv run alembic upgrade head` |
| `Connection refused` on port 5432 | Postgres port not exposed | Use dev overlay: add `-f docker-compose.dev.yml` |
| Whisper model download slow | First-time download (~1GB for `base`) | Wait, or set `WHISPER_MODEL=tiny` in `.env` for faster startup |
| Ollama `model not found` | Model not pulled | `ollama pull llama3.2:3b` |
| Keycloak not starting | Postgres not ready | Check `docker compose logs keycloak` — wait for postgres health check |
| CORS errors in browser | Frontend origin not in CORS_ORIGINS | Add your app origins (3000/3001/3002) to `CORS_ORIGINS` in `.env` |
| JWT validation fails | Keycloak not running or wrong issuer | Set `AUTH_ENABLED=false` in `.env` for local dev |
| `uv run alembic upgrade head` import error | Dependencies not synced | `cd backend && uv sync` |
| Frontend `pnpm dev` fails | Node modules not installed | Run `pnpm install` first |
| Frontend `nuxt build` fails with `ELOOP: too many symbolic links` | pnpm symlink traversal in Nitro output | Build with `NITRO_NO_SYMLINKS=1 pnpm -F <app> build` |
| WebSocket disconnects immediately | Auth token missing/expired | Check browser console; ensure login or set `AUTH_ENABLED=false` |
| `docker compose` not found | Old Docker version | Install Docker Compose V2 (included with Docker Desktop) |
| Port already in use | Another service on same port | `lsof -i :PORT` to find and stop the conflicting process |
| Redis connection refused | Redis not started | Add `redis` to your `docker compose up` command |
| Alembic "Target database is not up to date" | Pending migrations | `uv run alembic upgrade head` |
| `uv: command not found` | uv not installed | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Resetting Everything

When you need a clean slate:

```bash
cd backend

# 1. Stop all containers
docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# 2. Remove database volume (destroys all data)
docker volume rm backend_postgres_data

# 3. Restart infrastructure
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama

# 4. Re-run migrations and seed
uv run alembic upgrade head
uv run python -m scripts.seed
```

Or to just reset data without removing the volume:

```bash
uv run python -m scripts.seed --reset
```

---

## Useful Commands Cheatsheet

| Task | Command |
|------|---------|
| Start infra (dev) | `cd backend && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama` |
| Start backend | `cd backend && ./run_backend.sh` |
| Start frontend | `cd frontend && pnpm dev` |
| Run migrations | `cd backend && uv run alembic upgrade head` |
| Create migration | `cd backend && uv run alembic revision --autogenerate -m "description"` |
| Seed database | `cd backend && uv run python -m scripts.seed` |
| Reset + re-seed | `cd backend && uv run python -m scripts.seed --reset` |
| Backend tests | `cd backend && uv run pytest tests/ -v` |
| Backend lint | `cd backend && uv run ruff check app/ && uv run ruff format app/` |
| Backend type check | `cd backend && uv run mypy app/` |
| Frontend tests | `cd frontend && pnpm test` |
| Frontend lint | `cd frontend && pnpm lint` |
| View DB logs | `docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f postgres` |
| Deploy (prod) | `cd backend && ./scripts/deploy.sh --full` |
| Backup DB | `cd backend && ./scripts/backup.sh` |
| Pull LLM model | `ollama pull llama3.2:3b` |
| Health check | `curl http://localhost:8000/health/ready` |

---

## Environment Variable Reference

All variables are configured in `backend/.env`. Defaults are suitable for local development.

| Variable | Default | Description |
|----------|---------|-------------|
| **Server** | | |
| `ENVIRONMENT` | `development` | Runtime environment (`development` / `production`) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG` / `INFO` / `WARNING` / `ERROR`) |
| **Database** | | |
| `DATABASE_URL` | `postgresql+asyncpg://horus:horus@localhost:5432/horus_db` | PostgreSQL async connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| **Authentication** | | |
| `AUTH_ENABLED` | `true` | Enable Keycloak JWT validation (`false` for dev without Keycloak) |
| `KEYCLOAK_ISSUER_URL` | `http://localhost:8180/realms/horus` | Keycloak realm issuer URL |
| `KEYCLOAK_CLIENT_ID` | `horus-api` | Keycloak client ID for the API |
| **LLM / AI** | | |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_LLM_MODEL` | `llama3.2:3b` | LLM model for ATC responses |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| **Speech** | | |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny` / `base` / `small` / `medium` / `large`) |
| `WHISPER_LANGUAGE` | `en` | STT language |
| `TTS_LANGUAGE` | `en` | TTS language |
| `SCENES_PATH` | _(blank)_ | Scene registry YAML; blank uses the packaged `default-v1` Scene |
| **Knowledge** | | |
| `KNOWLEDGE_CHUNK_SIZE` | `1000` | Ingest chunk window in tokens (contract: 1000/150) |
| `KNOWLEDGE_CHUNK_OVERLAP` | `150` | Tokens of overlap between consecutive chunks |
| `KNOWLEDGE_EMBEDDING_DIMENSIONS` | `768` | Expected embedding width; a mismatch is a hard ingest failure |
| `KNOWLEDGE_TOP_K` | `5` | Chunks returned per retrieval query |
| `KNOWLEDGE_DEFAULT_CHUNK_QUOTA` | `10` | Per-scope chunk budget, checked before embedding |
| **Telemetry** | | |
| `TRACE_RETENTION_DAYS` | `90` | Days of provenance events kept before the prune cron runs |
| `TRACE_LOG_LEVEL` | `INFO` | Log level for the telemetry module |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(unset)_ | OTLP collector endpoint; unset means the console exporter |
| `LLM_ALLOW_EXTERNAL_FALLBACK` | `false` | Permit falling back to an off-VPS provider (e.g. Groq) |
| **Audio** | | |
| `SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `CHUNK_SIZE` | `1024` | Audio chunk size |
| `AUDIO_FORMAT` | `wav` | Audio output format |
| `ENABLE_RADIO_EFFECTS` | `true` | Apply radio-effect audio processing |
| `NOISE_LEVEL` | `0.02` | Radio noise intensity |
| `STATIC_LEVEL` | `0.01` | Radio static intensity |
| **CORS** | | |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3000` | Comma-separated allowed origins |

---

## Architecture Decisions

See `docs/architecture/ARCHITECTURE-INDEX.md` for the full decision → ADR → status
table. The records are:

- [ADR-001: Monorepo Structure](architecture/ADR-001-monorepo-structure.md)
- [ADR-002: Database Selection](architecture/ADR-002-database-postgresql.md)
- [ADR-003: Deployment Architecture](architecture/ADR-003-deployment-architecture.md)
- [ADR-004: LangGraph Multi-Agent Architecture](architecture/ADR-004-langgraph-multi-agent.md)
- [ADR-005: Flight Plan Pipeline](architecture/ADR-005-flight-plan-pipeline.md)
- [ADR-006: Scene/Session Split and Persistent LangGraph State](architecture/ADR-006-scene-session-and-persistent-langgraph.md)
- [ADR-007: LLM Provider Adapters](architecture/ADR-007-llm-provider-adapters.md)
- [ADR-008: Tenant-Scoped Knowledge and pgvector Retrieval](architecture/ADR-008-tenant-scoped-knowledge-and-pgvector-retrieval.md)
- [ADR-009: OpenTelemetry and Postgres Trace](architecture/ADR-009-opentelemetry-and-postgres-trace.md)

## Session Lifecycle and the Composition Root

There is no `HorusOrchestrator`. The caller-facing lifecycle seam is
`TrainingSessionModule` in `backend/app/services/training_sessions/session_module.py`,
with six public methods:

| Method | Purpose |
|---|---|
| `start(StartSessionCommand)` | Run validation, persist state, return a `SessionSnapshot` |
| `validate(*, user_id, flight_plan, language, org_id)` | Run pre-flight validation for a flight plan with no session and nothing persisted. `org_id` is optional; a `None` tenant makes retrieval fail-closed to platform-wide chunks only |
| `send(SendTransmissionCommand)` | Run one pilot → ATC exchange |
| `await_instructor(org_id, session_id, instructor_response)` | Complete a held exchange — with the instructor's text if given, otherwise by resuming the graph non-interrupting |
| `end(EndSessionCommand)` | Run scoring, return a `Debrief` |
| `snapshot(session_id, org_id)` | Read the persisted state |

Callers never see `HorusState`, a LangGraph `thread_id`, or `interrupt_before`.

**`backend/app/main.py` is the composition root.** Its `lifespan` builds every
long-lived collaborator exactly once and publishes it on `app.state`: the
`LLMModule`, the `SessionStore`, the Scene registry, the `KnowledgeRetriever`,
the trace recorder, and finally the `TrainingSessionModule`. Nothing below
`main.py` constructs a session store or an LLM client. In production the store
is `PostgresSessionStore` (a LangGraph PostgreSQL checkpointer); in every other
environment it is `InMemorySessionStore`.

See [ADR-006](architecture/ADR-006-scene-session-and-persistent-langgraph.md).
