# Horus Development Guide

Complete guide for setting up and working on the Horus Aviation Training Platform.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10–3.11 | Backend runtime |
| Node.js | 20+ | Frontend build |
| pnpm | 9+ | Frontend package manager |
| uv | latest | Python package manager |
| Ollama | latest | Local LLM inference |
| PostgreSQL | 16 (via Docker) | Database |
| Docker + Compose | latest | Backend stack |

## Quick Start (Local Development)

### 1. Clone and set up

```bash
git clone <repo-url>
cd horus-mvp
```

### 2. Start the backend stack

```bash
cd backend

# Copy and configure environment
cp .env.docker.example .env.docker
# Edit .env.docker to set CORS_ORIGINS to http://localhost:3000

# Start PostgreSQL + Ollama via Docker Compose
docker compose up postgres ollama -d

# Set up Python environment
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 3. Pull the Ollama model

```bash
# In a separate terminal (takes a few minutes)
ollama pull llama3:latest
```

### 4. Start the frontend

```bash
cd frontend
pnpm install
pnpm dev
# Opens at http://localhost:3000
```

---

## Backend Development

### Running tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v                          # all tests
pytest tests/unit/ -v                    # unit tests only
pytest tests/integration/ -v             # integration tests only
pytest tests/ --cov=app --cov-report=term-missing  # with coverage
```

### Linting and formatting

```bash
cd backend
ruff check app/          # lint
ruff check app/ --fix    # auto-fix lint issues
ruff format app/         # format
mypy app/                # type check
```

### Adding a new API endpoint

See [`.github/copilot/skills/add-api-endpoint.md`](../.github/copilot/skills/add-api-endpoint.md) for a complete walkthrough.

### Adding a database model

See [`.github/copilot/skills/add-db-model.md`](../.github/copilot/skills/add-db-model.md) for a complete walkthrough including Alembic migrations.

### Database migrations

```bash
# After changing any model in app/models/
alembic revision --autogenerate -m "describe_your_change"
alembic upgrade head

# Check current migration state
alembic current

# Downgrade one step
alembic downgrade -1
```

---

## Frontend Development

### Running tests

```bash
cd frontend
pnpm test          # run once
pnpm test:watch    # watch mode
```

### Linting and formatting

```bash
cd frontend
pnpm lint          # ESLint check
pnpm lint:fix      # auto-fix
pnpm format        # Prettier format
```

### Adding a new component

See [`.github/copilot/skills/add-vue-component.md`](../.github/copilot/skills/add-vue-component.md) for the component template and naming conventions.

### Environment variables (local)

The frontend uses `useRuntimeConfig()` to access backend URLs. In development, defaults to `localhost`:
- `NUXT_PUBLIC_API_URL` → `http://localhost:8000`
- `NUXT_PUBLIC_WS_URL` → `ws://localhost:8000/ws/voice`

No `.env` file needed locally unless you want to override these.

---

## Production Deployment

### Backend (VPS)

```bash
cd backend

# 1. Copy and configure the Docker env file
cp .env.docker.example .env.docker
# Edit .env.docker — set CORS_ORIGINS to your Cloudflare Pages domain

# 2. Start the full stack
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Pull the Ollama model (first time only)
docker compose exec ollama ollama pull llama3:latest
```

Check health: `curl https://your-vps-domain/health/ready`

> You'll need a reverse proxy (nginx or Caddy) in front of port 8000 for TLS termination.

### Frontend (Cloudflare Pages)

1. Connect your GitHub repo to Cloudflare Pages
2. Build settings:
   - **Framework preset**: None (custom)
   - **Build command**: `cd frontend && pnpm install && pnpm build`
   - **Build output directory**: `frontend/.output/public`
3. Environment variables (set in Cloudflare dashboard):
   - `CF_PAGES=1`
   - `NUXT_PUBLIC_API_URL=https://api.yourdomain.com`
   - `NUXT_PUBLIC_WS_URL=wss://api.yourdomain.com/ws/voice`

---

## Project Structure

```
horus-mvp/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── api/routes/         # HTTP route handlers
│   │   ├── api/v1/             # Versioned REST routes
│   │   ├── core/               # Audio pipeline + WebSocket manager
│   │   ├── db/                 # SQLAlchemy session + repositories
│   │   ├── models/             # ORM models (TrainingSession, VoiceLog, Scenario)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   └── services/           # STT, TTS, LLM, audio effects
│   ├── tests/                  # pytest test suite
│   ├── alembic/                # Database migrations
│   ├── docker/                 # Dockerfile
│   ├── docker-compose.yml      # Production stack
│   └── docker-compose.dev.yml  # Dev overrides
│
└── frontend/                   # Nuxt 4 frontend (Cloudflare Pages)
    ├── app/
    │   ├── pages/              # Auto-routed pages
    │   ├── components/ui/      # H-prefixed design system
    │   ├── components/shared/  # Layout components
    │   └── composables/        # Vue Composition API state
    ├── nuxt.config.ts          # Nuxt + Cloudflare Pages config
    └── wrangler.toml           # Cloudflare Pages project config
```

---

## Debugging the Audio Pipeline

See [`.github/copilot/skills/debug-audio-pipeline.md`](../.github/copilot/skills/debug-audio-pipeline.md) for a step-by-step debug checklist.

## Architecture Decisions

See `docs/architecture/` for Architecture Decision Records (ADRs):
- [ADR-001: Monorepo Structure](architecture/ADR-001-monorepo-structure.md)
- [ADR-002: Database Selection](architecture/ADR-002-database-postgresql.md)
- [ADR-003: Deployment Architecture](architecture/ADR-003-deployment-architecture.md)
