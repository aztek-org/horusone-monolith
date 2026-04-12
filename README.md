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

```bash
# 1. Setup
./setup.sh

# 2. Start infrastructure
cd backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis ollama

# 3. Migrate + seed
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed

# 4. Start backend
./run_backend.sh

# 5. Start frontend apps (new terminal)
cd frontend
pnpm install
pnpm dev
```

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
│   ├── scripts/                    # deploy.sh, backup.sh, restore.sh, seed.py
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
| `backend/docker/init-multiple-dbs.sh` | First-boot Postgres init for `keycloak_db` |

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
