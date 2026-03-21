# Horus — Development Guide

Complete guide for setting up and working on the Horus Aviation Training Platform.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10–3.11 | Backend runtime |
| Node.js | 20+ | Frontend build |
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

# 3. Activate venv, run migrations, seed data
source .venv/bin/activate
alembic upgrade head
python -m scripts.seed

# 4. Pull Ollama model (first time — takes a few minutes)
ollama pull llama3.2:3b

# 5. Start the backend
./run_backend.sh

# 6. Start the frontend (new terminal)
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

> **💡 Tip:** Set `AUTH_ENABLED=false` in `backend/.env` to skip Keycloak and get a dev user automatically. This is the easiest way to develop locally.

---

## Architecture Overview

Horus uses a 5-layer architecture:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Edge** | Traefik + Keycloak 24 | Reverse proxy, TLS termination, identity/auth |
| **Realtime** | *(Planned)* Rust WebSocket gateway + Go event processor | Low-latency voice streaming |
| **Control** | Python/FastAPI + LangGraph AI agent | API, business logic, ATC AI pipeline |
| **Data** | PostgreSQL 16 + Redis 7 + *(Planned)* Qdrant | Persistence, caching, vector search |
| **Frontend** | Nuxt 4 + Vue 3 + TailwindCSS | SPA on Cloudflare Pages |

### Audio Pipeline

```
Microphone → WebSocket → Whisper STT → LangGraph/Ollama LLM → TTS → Radio Effects → WebSocket → Speaker
```

See [`.github/copilot/skills/debug-audio-pipeline.md`](../.github/copilot/skills/debug-audio-pipeline.md) for a step-by-step debug checklist.

---

## Project Structure

```
horus-mvp/
├── backend/                        # FastAPI Python backend (VPS)
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # Pydantic settings (env-based)
│   │   ├── api/routes/             # Route handlers (health, voice)
│   │   ├── core/                   # Audio pipeline + WebSocket manager
│   │   ├── db/                     # SQLAlchemy async session + repositories
│   │   ├── models/                 # ORM models (User, Organization, Seat, Scenario, etc.)
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   └── services/               # STT (Whisper), TTS, LLM (Ollama), audio effects
│   ├── tests/                      # pytest test suite (unit/ + integration/)
│   ├── alembic/                    # Database migrations
│   ├── scripts/                    # seed.py, deploy.sh, backup.sh, restore.sh
│   ├── docker/                     # Dockerfile + keycloak-import/
│   ├── docker-compose.yml          # Base service definitions
│   ├── docker-compose.dev.yml      # Dev overrides (exposed ports, hot reload)
│   ├── docker-compose.prod.yml     # Prod overrides (TLS, resource limits, GPU)
│   ├── run_backend.sh              # Dev convenience script
│   └── pyproject.toml              # uv package manager config
│
├── frontend/                       # Nuxt 4 frontend (Cloudflare Pages)
│   ├── app/
│   │   ├── pages/                  # Auto-routed pages
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
│   ├── development.md              # This file
│   ├── OLLAMA_SETUP.md             # LLM configuration guide
│   └── architecture/               # Architecture Decision Records (ADRs)
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
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed frontend origins |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small/medium/large) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

See the [Environment Variable Reference](#environment-variable-reference) at the end of this document for the full list.

### Database

PostgreSQL 16 runs via Docker with the dev compose overlay exposing port 5432.

```bash
# Start PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres

# Run all migrations
cd backend && source .venv/bin/activate
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe_your_change"

# Check current migration state
alembic current

# Downgrade one step
alembic downgrade -1
```

**Database tables:** `users`, `organizations`, `seats`, `scenarios`, `training_sessions`, `voice_logs`

**Seed data** (idempotent — safe to run repeatedly):

```bash
python -m scripts.seed              # insert seed data (skips existing rows)
python -m scripts.seed --reset      # truncate all tables, then re-seed
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

- **Keycloak admin console**: http://localhost:8080 (admin / admin)
- The `horus` realm is auto-imported on first start
- Frontend uses **OIDC PKCE flow** (no client secret)
- Backend validates **RS256 JWT tokens** with JWKS endpoint caching

### Running the Backend

```bash
cd backend && source .venv/bin/activate

# Option 1: convenience script (loads .env automatically)
./run_backend.sh

# Option 2: manual
uv run --env-file .env uvicorn app.main:app --reload
```

The API server starts at http://localhost:8000.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/ready` | Readiness check (verifies all services) |
| GET/POST | `/api/v1/scenarios` | List / create scenarios |
| GET/PUT/DELETE | `/api/v1/scenarios/{id}` | Scenario CRUD |
| GET/POST | `/api/v1/sessions` | List / create training sessions |
| GET | `/api/v1/sessions/{id}` | Get training session details |
| WebSocket | `/ws/voice` | Real-time voice communication |

### Adding Endpoints and Models

- **New API endpoint**: See [`.github/copilot/skills/add-api-endpoint.md`](../.github/copilot/skills/add-api-endpoint.md)
- **New database model**: See [`.github/copilot/skills/add-db-model.md`](../.github/copilot/skills/add-db-model.md)

---

## Frontend Setup (Detailed)

### Installation

```bash
cd frontend
pnpm install
pnpm dev        # http://localhost:3000
```

### Environment

Runtime config is set via `nuxt.config.ts` with sensible localhost defaults. No `.env` file needed for local dev unless you want to override:

- `NUXT_PUBLIC_API_URL` → defaults to `http://localhost:8000`
- `NUXT_PUBLIC_WS_URL` → defaults to `ws://localhost:8000/ws/voice`

For production, set `NUXT_PUBLIC_*` env vars in the Cloudflare Pages dashboard.

### Key Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | `index.vue` | Landing / home |
| `/login` | `login.vue` | Authentication |
| `/configurator` | `configurator.vue` | Scenario Architect — build training scenarios |
| `/library` | `library.vue` | Scenario Library — browse and select |
| `/performance` | `performance.vue` | Training analytics and session history |
| `/dashboard` | `dashboard.vue` | Organization admin dashboard |
| `/settings` | `settings.vue` | User settings |

### Design System

H-prefixed components live in `app/components/ui/`:

`HButton` · `HCard` · `HBadge` · `HSlider` · `HProgress` · `HCheckbox` · `HChecklistItem` · `HDropdown` · `HDataPanel` · `HSection` · `HStatusIndicator` · `HStatusPill` · `HLogEntry` · `HRadioGroup` · `HButtonGroup`

- Dark theme by default with `horus-*` and `atc-*` color tokens in `tailwind.config.ts`
- See [`.github/copilot/skills/add-vue-component.md`](../.github/copilot/skills/add-vue-component.md) for creating new components

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
| Keycloak | 8180 | `http://localhost:8080` |

### Full Stack (everything in Docker)

```bash
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Access via: `api.localhost` (backend), `auth.localhost` (Keycloak), `localhost:8080` (Traefik dashboard)

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
cd backend && source .venv/bin/activate

pytest tests/ -v                    # all tests
pytest tests/unit/ -v               # unit only
pytest tests/integration/ -v        # integration only
pytest tests/ --cov=app             # with coverage

ruff check app/                     # lint
ruff check app/ --fix               # auto-fix lint issues
ruff format app/                    # format
mypy app/                           # type check
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
| `python -m scripts.seed` hangs | PostgreSQL not running | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres` |
| `relation "users" does not exist` | Migrations not run | `alembic upgrade head` |
| `Connection refused` on port 5432 | Postgres port not exposed | Use dev overlay: add `-f docker-compose.dev.yml` |
| Whisper model download slow | First-time download (~1GB for `base`) | Wait, or set `WHISPER_MODEL=tiny` in `.env` for faster startup |
| Ollama `model not found` | Model not pulled | `ollama pull llama3.2:3b` |
| Keycloak not starting | Postgres not ready | Check `docker compose logs keycloak` — wait for postgres health check |
| CORS errors in browser | Frontend origin not in CORS_ORIGINS | Add `http://localhost:3000` to `CORS_ORIGINS` in `.env` |
| JWT validation fails | Keycloak not running or wrong issuer | Set `AUTH_ENABLED=false` in `.env` for local dev |
| `alembic upgrade head` import error | Not in venv or deps missing | `source .venv/bin/activate && uv pip install -e ".[dev]"` |
| Frontend `pnpm dev` fails | Node modules not installed | Run `pnpm install` first |
| WebSocket disconnects immediately | Auth token missing/expired | Check browser console; ensure login or set `AUTH_ENABLED=false` |
| `docker compose` not found | Old Docker version | Install Docker Compose V2 (included with Docker Desktop) |
| Port already in use | Another service on same port | `lsof -i :PORT` to find and stop the conflicting process |
| Redis connection refused | Redis not started | Add `redis` to your `docker compose up` command |
| Alembic "Target database is not up to date" | Pending migrations | `alembic upgrade head` |
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
source .venv/bin/activate
alembic upgrade head
python -m scripts.seed
```

Or to just reset data without removing the volume:

```bash
python -m scripts.seed --reset
```

---

## Useful Commands Cheatsheet

| Task | Command |
|------|---------|
| Start infra (dev) | `cd backend && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama` |
| Start backend | `cd backend && ./run_backend.sh` |
| Start frontend | `cd frontend && pnpm dev` |
| Run migrations | `cd backend && alembic upgrade head` |
| Create migration | `cd backend && alembic revision --autogenerate -m "description"` |
| Seed database | `cd backend && python -m scripts.seed` |
| Reset + re-seed | `cd backend && python -m scripts.seed --reset` |
| Backend tests | `cd backend && pytest tests/ -v` |
| Backend lint | `cd backend && ruff check app/ && ruff format app/` |
| Backend type check | `cd backend && mypy app/` |
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
| `KEYCLOAK_ISSUER_URL` | `http://localhost:8080/realms/horus` | Keycloak realm issuer URL |
| `KEYCLOAK_CLIENT_ID` | `horus-api` | Keycloak client ID for the API |
| **LLM / AI** | | |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_LLM_MODEL` | `llama3.2:3b` | LLM model for ATC responses |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| **Speech** | | |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny` / `base` / `small` / `medium` / `large`) |
| `WHISPER_LANGUAGE` | `en` | STT language |
| `TTS_LANGUAGE` | `en` | TTS language |
| **Audio** | | |
| `SAMPLE_RATE` | `16000` | Audio sample rate (Hz) |
| `CHUNK_SIZE` | `1024` | Audio chunk size |
| `AUDIO_FORMAT` | `wav` | Audio output format |
| `ENABLE_RADIO_EFFECTS` | `true` | Apply radio-effect audio processing |
| `NOISE_LEVEL` | `0.02` | Radio noise intensity |
| `STATIC_LEVEL` | `0.01` | Radio static intensity |
| **CORS** | | |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins |

---

## Architecture Decisions

See `docs/architecture/` for Architecture Decision Records (ADRs):

- [ADR-001: Monorepo Structure](architecture/ADR-001-monorepo-structure.md)
- [ADR-002: Database Selection](architecture/ADR-002-database-postgresql.md)
- [ADR-003: Deployment Architecture](architecture/ADR-003-deployment-architecture.md)
