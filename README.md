```text
██╗  ██╗ ██████╗ ██████╗ ██╗   ██╗███████╗ ██████╗ ███╗   ██╗███████╗
██║  ██║██╔═══██╗██╔══██╗██║   ██║██╔════╝██╔═══██╗████╗  ██║██╔════╝
███████║██║   ██║██████╔╝██║   ██║███████╗██║   ██║██╔██╗ ██║█████╗  
██╔══██║██║   ██║██╔══██╗██║   ██║╚════██║██║   ██║██║╚██╗██║██╔══╝  
██║  ██║╚██████╔╝██║  ██║╚██████╔╝███████║╚██████╔╝██║ ╚████║███████╗
╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝

                 HorusOne
```

# 🛩️ Horus — AI-Powered Aviation Training Platform

Real-time ATC voice communication practice powered by LLM inference, speech recognition, and text-to-speech audio processing.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Nuxt](https://img.shields.io/badge/Nuxt-4.x-00DC82.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)
![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)

## ✨ Features

- **Role-routed frontend apps**: Hangar (student), Tower (org admin/instructor), Squawk (platform admin)
- **Real-time ATC voice communication** via WebSocket with STT → LLM → TTS → radio effects
- **ICAO phraseology training** with scenario types across ground, departure, enroute, approach, and landing
- **LangGraph multi-agent orchestration** with 3 sub-graphs and 9 specialized agents
- **Session lifecycle + auditability** including completion flow, replay timeline, and event history
- **Student analytics and exports** for stats, transcripts (replay + stats), and assessment result payloads
- **Performance intelligence** with live trend bars, dynamic streak achievements, and server-side range loading
- **Org and platform operations** for seat/user/org management, progress visibility, and billing profile controls
- **Strict multi-tenant boundaries** with organization-scoped APIs and role-based access controls
- **Local-first inference** with Ollama (default `llama3.2:3b`) and no required cloud LLM key

## 🏗️ Tech Stack

| Layer | Technology | Deployment |
|-------|-----------|------------|
| Frontend | Nuxt 4 + Vue 3 + TailwindCSS | Cloudflare Pages |
| Backend | FastAPI + Python 3.11 | VPS (Docker Compose) |
| AI Pipeline | LangGraph + Ollama (9 agents, 3 sub-graphs) | VPS (Docker) |
| Database | PostgreSQL 16 (SQLAlchemy 2 async) | VPS (Docker) |
| Cache | Redis 7 | VPS (Docker) |
| Auth | Keycloak 24 (OIDC/JWT) | VPS (Docker) |
| LLM | Ollama (llama3.2) | VPS (Docker) |
| STT | OpenAI Whisper | VPS |
| TTS | Coqui TTS / gTTS | VPS |
| Proxy | Traefik v3 (TLS via Let's Encrypt) | VPS (Docker) |

## 🚀 Quick Start

Prerequisites: Docker (Compose v2), Python 3.10/3.11, Node.js 22+, FFmpeg + libsndfile.
`setup.sh` installs `uv` and `pnpm` if they are missing.

```bash
make setup     # deps, backend/.env, Docker infra, migrations, seed, Ollama models
make up        # infra + backend (:8000) + frontends (:3000-3002) in the background
make info      # what is running, where, DB counts, Ollama models
make down      # stop everything (data volumes are kept)
```

Run `make` with no arguments for every command, grouped by area. The ones you will use most:

| Command | What it does |
|---------|--------------|
| `make up-infra` | Start only Docker infra (postgres, redis, ollama, keycloak) |
| `make backend` / `make frontend` | Run one side in the foreground (after `make up-infra`) |
| `make logs-backend` / `make logs-frontend` | Follow the logs of processes started by `make up` |
| `make health` | Liveness + readiness of the backend |
| `make migrate` · `make migrate-create MSG="..."` | Apply / autogenerate Alembic migrations |
| `make seed` · `make db-reset` | Seed demo data (idempotent) · wipe Postgres and start over |
| `make test-unit` | Backend tests that need no infrastructure |
| `make test` | Backend (incl. Postgres tests, against a separate `horus_test` DB) + frontend tests |
| `make lint` · `make typecheck` · `make format` | Ruff/ESLint · mypy · Ruff/Prettier |

Notes:

- `make up` needs ports 8000, 3000, 3001 and 3002 free and refuses to start otherwise
  (the frontend dev proxy is hard-wired to `localhost:8000`).
- Already running Ollama on the host? Use `make up OLLAMA_HOST=1` (and `make setup OLLAMA_HOST=1`)
  so the Ollama container does not fight it for port 11434.
- Doing it by hand instead: see [`docs/development.md`](docs/development.md).

Open one of the frontend apps:

- [http://localhost:3000](http://localhost:3000) — squawk
- [http://localhost:3001](http://localhost:3001) — tower
- [http://localhost:3002](http://localhost:3002) — hangar

> **💡 Tip:** Set `AUTH_ENABLED=false` in `backend/.env` to skip Keycloak auth for local development.

📖 **Full setup guide**: [`docs/development.md`](docs/development.md)

## 📁 Project Structure

```
horus-mvp/
├── backend/                        # FastAPI control layer
│   ├── app/
│   │   ├── api/v1/                 # Versioned REST endpoints
│   │   ├── core/                   # Voice pipeline + websocket manager
│   │   ├── db/                     # Async session + repositories
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response contracts
│   │   └── services/               # STT, TTS, LLM, audio effects
│   ├── alembic/                    # DB migrations
│   ├── scripts/                    # deploy.sh, backup.sh, restore.sh, smoke-first-boot.sh, seed.py
│   ├── docker/                     # Dockerfiles and init scripts
│   └── tests/                      # pytest unit/integration suite
│
├── frontend/                       # Nuxt workspace monorepo
│   ├── apps/
│   │   ├── hangar/                 # Student app + auth gateway
│   │   ├── tower/                  # Org admin / instructor app
│   │   └── squawk/                 # Platform admin app
│   ├── packages/
│   │   └── core/                   # Shared UI, composables, layouts
│   ├── pnpm-workspace.yaml
│   └── turbo.json
│
├── docs/                           # Canonical docs + ADRs
└── .github/skills/                 # Reusable implementation/security skills
```

## 🧰 Maintained Scripts

| Script | Purpose |
|--------|---------|
| `./setup.sh` | One-command local bootstrap (prereqs, deps, env scaffolding) |
| `backend/run_backend.sh` | Start backend with `uv run` and `.env` loading |
| `backend/scripts/deploy.sh` | Production deployment helper (`--full`, `--skip-migrations`) |
| `backend/scripts/backup.sh` | PostgreSQL backups with retention pruning |
| `backend/scripts/restore.sh` | Interactive PostgreSQL restore from `.sql` / `.sql.gz` |
| `backend/scripts/smoke-first-boot.sh` | Verify Postgres first-boot init creates `keycloak_db` |
| `backend/docker/init-multiple-dbs.sh` | First-boot Postgres init for `keycloak_db` |
| `backend/docker/Dockerfile.postgres` | Postgres image with the init script baked in (executable) |
| `backend/docker/Dockerfile.keycloak` | Keycloak image with the realm JSON baked in |
| `backend/docker/keycloak-import/horus-realm.json` | Single source of truth for the Keycloak realm |

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Documentation Index](docs/README.md) | Canonical documentation map and structure conventions |
| [Development Guide](docs/development.md) | Full setup, architecture, testing, deployment, troubleshooting |
| [Ollama Setup](docs/OLLAMA_SETUP.md) | LLM model configuration and optimization |
| [ADR-001](docs/architecture/ADR-001-monorepo-structure.md) | Monorepo structure decision |
| [ADR-002](docs/architecture/ADR-002-database-postgresql.md) | Database selection (PostgreSQL) |
| [ADR-003](docs/architecture/ADR-003-deployment-architecture.md) | Deployment architecture |
| [ADR-004](docs/architecture/ADR-004-langgraph-multi-agent.md) | LangGraph multi-agent architecture (9 agents, 3 graphs) |
| [ADR-005](docs/architecture/ADR-005-flight-plan-pipeline.md) | Flight plan pipeline (form/text/image -> validate -> activate) |

## 📄 License

MIT
