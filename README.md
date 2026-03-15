# 🛩️ Horus — AI-Powered Aviation Training Platform

Real-time ATC voice communication practice powered by local LLM inference, speech recognition, and text-to-speech with radio-effect audio processing.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Nuxt](https://img.shields.io/badge/Nuxt-4.x-00DC82.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)
![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)

## ✨ Features

- **Real-time voice communication** with AI ATC controllers via WebSocket
- **ICAO standard phraseology** training with scenario-based exercises
- **Multiple scenario types** — ground, departure, enroute, approach, landing
- **Multi-tenant organization support** — users, organizations, seats, roles
- **Performance analytics** and session history tracking
- **Radio-effect audio processing** — band-pass filters, static, noise for realism
- **Local LLM inference** via Ollama — no cloud API keys required

## 🏗️ Tech Stack

| Layer | Technology | Deployment |
|-------|-----------|------------|
| Frontend | Nuxt 4 + Vue 3 + TailwindCSS | Cloudflare Pages |
| Backend | FastAPI + Python 3.11 | VPS (Docker Compose) |
| Database | PostgreSQL 16 (SQLAlchemy 2 async) | VPS (Docker) |
| Cache | Redis 7 | VPS (Docker) |
| Auth | Keycloak 24 (OIDC/JWT) | VPS (Docker) |
| LLM | Ollama + LangGraph | VPS (Docker) |
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
source .venv/bin/activate
alembic upgrade head && python -m scripts.seed

# 4. Start backend
./run_backend.sh

# 5. Start frontend (new terminal)
cd frontend && pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

> **💡 Tip:** Set `AUTH_ENABLED=false` in `backend/.env` to skip Keycloak auth for local development.

📖 **Full setup guide**: [`docs/development.md`](docs/development.md)

## 📁 Project Structure

```
horus-mvp/
├── backend/                    # FastAPI Python backend (VPS)
│   ├── app/                    # Application code
│   │   ├── api/routes/         # HTTP + WebSocket handlers
│   │   ├── models/             # SQLAlchemy ORM (User, Org, Scenario, etc.)
│   │   ├── services/           # STT, TTS, LLM, audio effects
│   │   └── db/                 # Session + repositories
│   ├── scripts/                # seed, deploy, backup, restore
│   ├── docker-compose*.yml     # Base, dev, and prod compose files
│   └── tests/                  # pytest (unit + integration)
│
├── frontend/                   # Nuxt 4 frontend (Cloudflare Pages)
│   ├── app/
│   │   ├── pages/              # Auto-routed pages
│   │   ├── components/ui/      # H-prefixed design system
│   │   └── composables/        # Vue Composition API state
│   ├── nuxt.config.ts
│   └── wrangler.toml           # Cloudflare Pages config
│
└── docs/                       # Documentation + ADRs
```

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Development Guide](docs/development.md) | Full setup, architecture, testing, deployment, troubleshooting |
| [Ollama Setup](docs/OLLAMA_SETUP.md) | LLM model configuration and optimization |
| [ADR-001](docs/architecture/ADR-001-monorepo-structure.md) | Monorepo structure decision |
| [ADR-002](docs/architecture/ADR-002-database-postgresql.md) | Database selection (PostgreSQL) |
| [ADR-003](docs/architecture/ADR-003-deployment-architecture.md) | Deployment architecture |

## 📄 License

MIT
