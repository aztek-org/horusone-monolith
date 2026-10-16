# ═══════════════════════════════════════════════════════════════════════════════
# Horus MVP — Project Makefile
# ═══════════════════════════════════════════════════════════════════════════════
#
# Run `make` (or `make help`) for the full, grouped list of commands.
#
# ── Prerequisites ────────────────────────────────────────────────────────────
#   Docker + Docker Compose v2   infrastructure (postgres, redis, ollama, keycloak)
#   Python 3.10 or 3.11 + uv     backend   (setup.sh installs uv if missing)
#   Node.js 22+ + pnpm           frontend  (setup.sh installs pnpm if missing)
#   FFmpeg + libsndfile          voice pipeline (whisper / TTS)
#   lsof, curl                   process management and health checks
#
# ── Quick start (fresh clone) ────────────────────────────────────────────────
#   make setup      install deps, create backend/.env, start infra,
#                   migrate, seed, pull Ollama models
#   make up         start infra + backend (:8000) + frontends (:3000-3002)
#   make info       see what is running and where
#   make down       stop everything
#
# ── How `make up` runs things ────────────────────────────────────────────────
#   Infrastructure runs in Docker (compose project in backend/, dev override
#   publishes postgres on :5432 and keycloak on :8180). The backend (uvicorn
#   --reload) and the frontends (turbo → 3× nuxt dev) run as background host
#   processes; their output goes to logs/backend.log and logs/frontend.log
#   (`make logs-backend`, `make logs-frontend`). `make down` stops them by
#   port, then stops the containers (volumes are kept).
#
#   Ports 8000, 3000, 3001 and 3002 must be free — the frontend dev proxy is
#   hard-wired to http://localhost:8000. `make up` refuses to start otherwise.
#
# ── Variables (override on the command line: make up OLLAMA_HOST=1) ─────────
#   OLLAMA_HOST=1       use a host-installed Ollama instead of the container
#                       (both bind :11434, so only one can run)
#   OLLAMA_MODEL        chat model pulled by `make ollama-pull`   (llama3.2:3b)
#   OLLAMA_EMBED_MODEL  embedding model pulled by `make ollama-pull`
#                       (nomic-embed-text) — keep both in step with
#                       LLM_MODEL / LLM_EMBEDDING_MODEL in backend/.env
#   TEST_DB             database the Postgres-backed tests run against
#                       (horus_test, created and migrated on demand — kept
#                       apart from horus_db because some tests leave rows behind)
#   MSG=…               migration message for `make migrate-create`
#   FILE=…              backup file for `make restore`
#
# ═══════════════════════════════════════════════════════════════════════════════

PATH := $(HOME)/.local/bin/:$(PATH)
SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Config ────────────────────────────────────────────────────────────────────
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod
# Compose names volumes after the directory holding the compose files.
COMPOSE_PROJECT := backend
BACKEND_DIR := backend
FRONTEND_DIR := frontend
LOG_DIR := logs
# `dev` is an optional extra (pytest, ruff, mypy), not a dependency group, so it
# has to be requested explicitly or the tooling never gets installed.
UV_RUN := cd $(BACKEND_DIR) && uv run --extra dev
OLLAMA_MODEL ?= llama3.2:3b
OLLAMA_EMBED_MODEL ?= nomic-embed-text
TEST_DB ?= horus_test
TEST_DATABASE_URL := postgresql+asyncpg://horus:horus@localhost:5432/$(TEST_DB)

BACKEND_PORT := 8000
FRONTEND_PORTS := 3000 3001 3002

OLLAMA_HOST ?= 0
ifeq ($(OLLAMA_HOST),1)
  INFRA_SERVICES := postgres redis keycloak
else
  INFRA_SERVICES := postgres redis ollama keycloak
endif

# ── Colors ────────────────────────────────────────────────────────────────────
CYAN := $(shell printf '\033[36m')
GREEN := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
RED := $(shell printf '\033[31m')
DIM := $(shell printf '\033[2m')
BOLD := $(shell printf '\033[1m')
RESET := $(shell printf '\033[0m')

# ── Helpers ───────────────────────────────────────────────────────────────────
# Wait up to 60s for PostgreSQL in the dev compose project to accept connections.
define wait_for_postgres
	@cd $(BACKEND_DIR) && _n=0; until $(COMPOSE_DEV) exec -T postgres pg_isready -U horus -d horus_db -q 2>/dev/null; do \
		_n=$$((_n + 1)); \
		if [ $$_n -ge 60 ]; then \
			echo "$(RED)✘ PostgreSQL not ready after 60s$(RESET) — run $(CYAN)make logs$(RESET) for details"; exit 1; \
		fi; \
		sleep 1; \
	done
endef

# Fail fast with a hint when PostgreSQL is not running.
define require_postgres
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T postgres pg_isready -U horus -d horus_db -q 2>/dev/null \
		|| { echo "$(RED)✘ PostgreSQL is not running$(RESET) — start it with $(CYAN)make up-infra$(RESET)"; exit 1; }
endef

# Create $(TEST_DB) if missing and bring it to the latest migration.
define prepare_test_db
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T postgres psql -U horus -d horus_db -tAc \
		"SELECT 1 FROM pg_database WHERE datname = '$(TEST_DB)'" | grep -q 1 \
		|| $(COMPOSE_DEV) exec -T postgres createdb -U horus $(TEST_DB)
	@export DATABASE_URL=$(TEST_DATABASE_URL); $(UV_RUN) alembic upgrade head >/dev/null 2>&1
endef

# True when something (any user, any process) is listening on 127.0.0.1:$(1).
port_in_use = (exec 3<>/dev/tcp/127.0.0.1/$(1)) 2>/dev/null

# ══════════════════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════════════════
# Generated from the `##@ Section` headers and `target: ## description` comments
# below, so documenting a target is a matter of adding a `##` comment to it.

.PHONY: help
help: ## Show this help
	@printf "\n  $(BOLD)🛩️  Horus MVP$(RESET) — AI-Powered Aviation Training Platform\n"
	@printf "  $(DIM)Usage: make <target> [VAR=value]   ·   variables are documented at the top of the Makefile$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@/ { printf "\n  $(BOLD)%s$(RESET)\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*?## / { printf "    $(CYAN)make %-18s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@printf "\n"

##@ Setup

.PHONY: setup
setup: ## First-time setup: deps, backend/.env, infra, migrations, seed, models
	@echo "$(BOLD)═══ Horus MVP — Setup ═══$(RESET)"
	@command -v docker >/dev/null || { echo "$(RED)✘ Docker not found$(RESET) — install Docker Engine + Compose v2"; exit 1; }
	@echo "$(CYAN)▸ Starting infrastructure ($(INFRA_SERVICES))...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d $(INFRA_SERVICES)
ifneq ($(OLLAMA_HOST),1)
	@# setup.sh probes :11434 and aborts if nothing answers, so let the container come up first.
	@_n=0; until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do \
		_n=$$((_n + 1)); [ $$_n -ge 60 ] && { echo "$(RED)✘ Ollama container not answering on :11434$(RESET)"; exit 1; }; sleep 1; \
	done
endif
	@./setup.sh
	@echo ""
	@echo "$(CYAN)▸ Waiting for PostgreSQL...$(RESET)"
	$(wait_for_postgres)
	@echo "$(CYAN)▸ Running migrations...$(RESET)"
	@$(UV_RUN) alembic upgrade head
	@echo ""
	@echo "$(CYAN)▸ Seeding database...$(RESET)"
	@$(UV_RUN) python -m scripts.seed
	@echo ""
	@$(MAKE) --no-print-directory ollama-pull
	@echo ""
	@echo "$(GREEN)$(BOLD)✓ Setup complete!$(RESET) Run $(CYAN)make up$(RESET) to start developing."

.PHONY: install
install: install-backend install-frontend ## Install all dependencies

.PHONY: install-backend
install-backend: ## Install backend Python deps (incl. dev tools: pytest, ruff, mypy)
	@echo "$(CYAN)Installing backend dependencies...$(RESET)"
	@cd $(BACKEND_DIR) && uv sync --extra dev --quiet
	@echo "$(GREEN)✓$(RESET) Backend deps installed"

.PHONY: install-frontend
install-frontend: ## Install frontend Node deps (pnpm workspace)
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm install --silent
	@echo "$(GREEN)✓$(RESET) Frontend deps installed"

##@ Development

.PHONY: up
up: ## Start infra + backend + frontends in the background (OLLAMA_HOST=1 for host Ollama)
	@echo "$(BOLD)═══ Starting Horus dev environment ═══$(RESET)"
	@_busy=""; for p in $(BACKEND_PORT) $(FRONTEND_PORTS); do \
		if $(call port_in_use,$$p); then _busy="$$_busy $$p"; fi; \
	done; \
	if [ -n "$$_busy" ]; then \
		echo "$(RED)✘ Port(s)$$_busy already in use.$(RESET)"; \
		echo "  If Horus is already running, use $(CYAN)make info$(RESET) / $(CYAN)make down$(RESET);"; \
		echo "  otherwise stop whatever holds them (e.g. $(CYAN)ss -ltnp | grep :8000$(RESET))."; \
		exit 1; \
	fi
ifeq ($(OLLAMA_HOST),1)
	@echo "  $(YELLOW)▸ Ollama: using host installation (http://localhost:11434)$(RESET)"
else
	@echo "  $(DIM)▸ Ollama: Docker container (use OLLAMA_HOST=1 for host)$(RESET)"
endif
	@echo ""
	@echo "$(CYAN)▸ Starting infrastructure ($(INFRA_SERVICES))...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d $(INFRA_SERVICES)
	@echo ""
	@echo "$(CYAN)▸ Waiting for PostgreSQL...$(RESET)"
	$(wait_for_postgres)
	@echo "$(GREEN)✓$(RESET) PostgreSQL ready"
	@echo ""
	@echo "$(CYAN)▸ Running migrations...$(RESET)"
	@$(UV_RUN) alembic upgrade head 2>&1 | tail -2
	@echo ""
	@mkdir -p $(LOG_DIR)
	@echo "$(CYAN)▸ Starting backend (port $(BACKEND_PORT), log: $(LOG_DIR)/backend.log)...$(RESET)"
	@# Redirect the whole subshell, not just the command, so no inherited fd keeps
	@# a caller's pipe (e.g. `make up | tee`) open after make exits.
	@($(UV_RUN) uvicorn app.main:app --reload --port $(BACKEND_PORT)) < /dev/null > $(LOG_DIR)/backend.log 2>&1 &
	@_n=0; until curl -sf http://localhost:$(BACKEND_PORT)/health 2>/dev/null | grep -q horus-atc-api; do \
		_n=$$((_n + 1)); \
		if [ $$_n -ge 90 ]; then \
			echo "$(RED)✘ Backend did not become healthy within 90s$(RESET) — last log lines:"; \
			tail -20 $(LOG_DIR)/backend.log; exit 1; \
		fi; \
		sleep 1; \
	done
	@echo "$(GREEN)✓$(RESET) Backend healthy (PID: $$(lsof -ti :$(BACKEND_PORT) 2>/dev/null | head -1 || echo '?'))"
	@echo ""
	@echo "$(CYAN)▸ Starting frontend apps (ports 3000/3001/3002, log: $(LOG_DIR)/frontend.log)...$(RESET)"
	@(cd $(FRONTEND_DIR) && pnpm dev) < /dev/null > $(LOG_DIR)/frontend.log 2>&1 &
	@_n=0; until $(call port_in_use,3000) && $(call port_in_use,3001) && $(call port_in_use,3002); do \
		_n=$$((_n + 1)); \
		if [ $$_n -ge 120 ]; then \
			echo "$(YELLOW)! Frontends not listening yet after 120s$(RESET) — check $(CYAN)make logs-frontend$(RESET)"; break; \
		fi; \
		sleep 1; \
	done
	@echo "$(GREEN)✓$(RESET) Frontend started $(DIM)(first page load compiles, give it a moment)$(RESET)"
	@echo ""
	@echo "$(GREEN)$(BOLD)═══ Horus is running! ═══$(RESET)"
	@echo ""
	@echo "  $(BOLD)Frontend$(RESET)   → $(CYAN)http://localhost:3000$(RESET) (squawk)"
	@echo "  $(BOLD)Frontend$(RESET)   → $(CYAN)http://localhost:3001$(RESET) (tower)"
	@echo "  $(BOLD)Frontend$(RESET)   → $(CYAN)http://localhost:3002$(RESET) (hangar)"
	@echo "  $(BOLD)Backend$(RESET)    → $(CYAN)http://localhost:$(BACKEND_PORT)$(RESET)"
	@echo "  $(BOLD)API Docs$(RESET)   → $(CYAN)http://localhost:$(BACKEND_PORT)/docs$(RESET)"
	@echo "  $(BOLD)Keycloak$(RESET)   → $(CYAN)http://localhost:8180$(RESET) $(DIM)(admin / admin)$(RESET)"
	@echo ""
	@echo "  $(DIM)Logs: make logs-backend · make logs-frontend · make logs   Stop: make down$(RESET)"

.PHONY: up-infra
up-infra: ## Start only the Docker infrastructure (postgres, redis, ollama, keycloak)
	@echo "$(CYAN)Starting infrastructure ($(INFRA_SERVICES))...$(RESET)"
ifeq ($(OLLAMA_HOST),1)
	@echo "  $(YELLOW)▸ Ollama: using host installation$(RESET)"
endif
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d $(INFRA_SERVICES)
	$(wait_for_postgres)
	@echo "$(GREEN)✓$(RESET) Infrastructure running"

.PHONY: up-full
up-full: ## Run everything in Docker instead (backend container + Traefik; no host processes)
	@echo "$(CYAN)Starting full Docker stack (builds the backend image)...$(RESET)"
	@echo "  $(DIM)Needs ports 80, 443, 8000, 8080, 8081 free; do not combine with make up.$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d --build
	@echo "$(GREEN)✓$(RESET) Full stack running — API http://localhost:8000 · Keycloak http://localhost:8180 · Traefik http://localhost:8081"

.PHONY: down
down: ## Stop backend, frontends and containers (data volumes are kept)
	@echo "$(BOLD)Stopping Horus...$(RESET)"
	@for p in $(BACKEND_PORT) $(FRONTEND_PORTS); do \
		_pids=$$(lsof -ti :$$p 2>/dev/null); \
		if [ -n "$$_pids" ]; then kill $$_pids 2>/dev/null; echo "$(GREEN)✓$(RESET) Stopped process on :$$p"; fi; \
	done
	@# [t] keeps pkill from matching (and killing) this recipe's own shell.
	@-pkill -f "[t]urbo run dev --parallel" 2>/dev/null || true
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) down 2>/dev/null
	@echo "$(GREEN)✓$(RESET) Infrastructure stopped"

.PHONY: restart
restart: ## Restart everything (down, then up)
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up

.PHONY: backend
backend: ## Run the backend in the foreground with reload (needs make up-infra)
	@if $(call port_in_use,$(BACKEND_PORT)); then echo "$(RED)✘ Port $(BACKEND_PORT) already in use$(RESET)"; exit 1; fi
	$(require_postgres)
	@echo "$(CYAN)Starting backend on port $(BACKEND_PORT)...$(RESET)"
	@$(UV_RUN) uvicorn app.main:app --reload --port $(BACKEND_PORT)

.PHONY: frontend
frontend: ## Run all three frontends in the foreground (squawk, tower, hangar)
	@echo "$(CYAN)Starting frontend apps on ports 3000/3001/3002...$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm dev

.PHONY: logs
logs: ## Follow Docker container logs
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) logs -f --tail=50

.PHONY: logs-backend
logs-backend: ## Follow the backend log written by make up
	@tail -n 50 -F $(LOG_DIR)/backend.log

.PHONY: logs-frontend
logs-frontend: ## Follow the frontend log written by make up
	@tail -n 50 -F $(LOG_DIR)/frontend.log

##@ Database

.PHONY: migrate
migrate: ## Apply all pending migrations
	$(require_postgres)
	@echo "$(CYAN)Running migrations...$(RESET)"
	@$(UV_RUN) alembic upgrade head
	@echo "$(GREEN)✓$(RESET) Migrations applied"

.PHONY: migrate-create
migrate-create: ## Autogenerate a migration: make migrate-create MSG="add_field"
	@if [ -z "$(MSG)" ]; then echo "$(RED)✘$(RESET) Usage: make migrate-create MSG=\"description\""; exit 1; fi
	$(require_postgres)
	@$(UV_RUN) alembic revision --autogenerate -m "$(MSG)"
	@echo "$(GREEN)✓$(RESET) Migration created — review it in $(BACKEND_DIR)/alembic/versions/"

.PHONY: migrate-down
migrate-down: ## Roll back the last migration
	$(require_postgres)
	@echo "$(YELLOW)⚠ Rolling back last migration...$(RESET)"
	@$(UV_RUN) alembic downgrade -1
	@echo "$(GREEN)✓$(RESET) Rolled back"

.PHONY: migrate-status
migrate-status: ## Show the current migration revision
	$(require_postgres)
	@$(UV_RUN) alembic current 2>/dev/null

.PHONY: seed
seed: ## Seed demo data (idempotent — safe to re-run)
	$(require_postgres)
	@$(UV_RUN) python -m scripts.seed

.PHONY: seed-reset
seed-reset: ## Delete seeded data and seed again
	$(require_postgres)
	@$(UV_RUN) python -m scripts.seed --reset

.PHONY: db-shell
db-shell: ## Open a psql shell on horus_db
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec postgres psql -U horus -d horus_db

.PHONY: db-reset
db-reset: ## ⚠ Wipe the Postgres volume (app + Keycloak DBs), re-migrate, re-seed
	@echo "$(RED)$(BOLD)⚠  This will destroy ALL PostgreSQL data (horus_db and keycloak_db)!$(RESET)"
	@echo "  $(DIM)Redis and Ollama volumes are left alone.$(RESET)"
	@read -p "  Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo ""
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) stop keycloak 2>/dev/null || true
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) rm -sf postgres
	@docker volume rm $(COMPOSE_PROJECT)_postgres_data >/dev/null 2>&1 || true
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d postgres
	@echo "$(CYAN)Waiting for PostgreSQL...$(RESET)"
	$(wait_for_postgres)
	@$(UV_RUN) alembic upgrade head
	@$(UV_RUN) python -m scripts.seed
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d keycloak
	@echo "$(GREEN)✓$(RESET) Database reset complete (Keycloak re-imports its realm on start)"

##@ Testing & Quality

.PHONY: test
test: test-backend test-frontend ## Run all tests

.PHONY: test-backend
test-backend: ## Run all backend tests, incl. Postgres ones against horus_test (needs make up-infra)
	$(require_postgres)
	@echo "$(BOLD)═══ Backend Tests ═══$(RESET)"
	$(prepare_test_db)
	@export DATABASE_URL=$(TEST_DATABASE_URL); $(UV_RUN) pytest tests/ -v

.PHONY: test-unit
test-unit: ## Run backend tests that need no infrastructure (Postgres tests skip)
	@echo "$(BOLD)═══ Backend Unit Tests ═══$(RESET)"
	@unset DATABASE_URL; $(UV_RUN) pytest tests/

.PHONY: test-frontend
test-frontend: ## Run frontend tests (vitest, all apps)
	@echo "$(BOLD)═══ Frontend Tests ═══$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm test

.PHONY: test-cov
test-cov: ## Run backend tests with a coverage report (needs make up-infra)
	$(require_postgres)
	$(prepare_test_db)
	@export DATABASE_URL=$(TEST_DATABASE_URL); $(UV_RUN) pytest tests/ --cov=app --cov-report=term-missing

.PHONY: lint
lint: lint-backend lint-frontend ## Lint everything

.PHONY: lint-backend
lint-backend: ## Lint backend (ruff check + format check)
	@echo "$(BOLD)═══ Backend Lint ═══$(RESET)"
	@$(UV_RUN) ruff check app/
	@$(UV_RUN) ruff format --check app/

.PHONY: lint-frontend
lint-frontend: ## Lint frontend (ESLint)
	@echo "$(BOLD)═══ Frontend Lint ═══$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm lint

.PHONY: format
format: format-backend format-frontend ## Format everything (rewrites files)

.PHONY: format-backend
format-backend: ## Format backend (ruff format)
	@$(UV_RUN) ruff format app/
	@echo "$(GREEN)✓$(RESET) Backend formatted"

.PHONY: format-frontend
format-frontend: ## Format frontend (Prettier)
	@cd $(FRONTEND_DIR) && pnpm format
	@echo "$(GREEN)✓$(RESET) Frontend formatted"

.PHONY: typecheck
typecheck: ## Type-check backend (mypy, same flags as CI)
	@$(UV_RUN) mypy app/ --ignore-missing-imports

.PHONY: check
check: lint test ## Lint + all tests (CI-like)

##@ Production

.PHONY: prod-up
prod-up: ## Start the production stack (needs backend/.env.prod)
	@test -f $(BACKEND_DIR)/.env.prod || { echo "$(RED)✘ $(BACKEND_DIR)/.env.prod missing$(RESET) — copy it from .env.prod.example"; exit 1; }
	@echo "$(BOLD)Starting production stack...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_PROD) up -d
	@echo "$(GREEN)✓$(RESET) Production running"

.PHONY: prod-down
prod-down: ## Stop the production stack
	@cd $(BACKEND_DIR) && $(COMPOSE_PROD) down

.PHONY: deploy
deploy: ## Deploy backend (rolling update via backend/scripts/deploy.sh)
	@cd $(BACKEND_DIR) && ./scripts/deploy.sh

.PHONY: deploy-full
deploy-full: ## Deploy everything (full rebuild)
	@cd $(BACKEND_DIR) && ./scripts/deploy.sh --full

.PHONY: backup
backup: ## Back up PostgreSQL databases to backend/backups/
	@cd $(BACKEND_DIR) && ./scripts/backup.sh

.PHONY: restore
restore: ## Restore a backup: make restore FILE=backups/xxx.sql.gz
	@if [ -z "$(FILE)" ]; then echo "$(RED)✘$(RESET) Usage: make restore FILE=backups/filename.sql.gz"; exit 1; fi
	@cd $(BACKEND_DIR) && ./scripts/restore.sh $(FILE)

##@ Info & Maintenance

.PHONY: info
info: ## Show containers, local processes, URLs, DB counts, Ollama models, tool versions
	@printf "\n"
	@printf "\033[1m═══════════════════════════════════════════════════════════\033[0m\n"
	@printf "\033[1m  🛩️  Horus MVP — Status\033[0m\n"
	@printf "\033[1m═══════════════════════════════════════════════════════════\033[0m\n"
	@printf "\n"
	@printf "  \033[1mDocker Containers\033[0m\n"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) ps --format "    {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "    \033[2mNo containers running\033[0m\n"
	@printf "\n"
	@printf "  \033[1mLocal Processes\033[0m\n"
	@if curl -sf http://localhost:$(BACKEND_PORT)/health 2>/dev/null | grep -q horus-atc-api; then printf "    \033[32m●\033[0m Backend    pid=$$(lsof -ti :$(BACKEND_PORT) | head -1)  \033[36mhttp://localhost:$(BACKEND_PORT)\033[0m\n"; \
		elif $(call port_in_use,$(BACKEND_PORT)); then printf "    \033[33m●\033[0m Backend    \033[33m:$(BACKEND_PORT) is held by something else\033[0m\n"; \
		else printf "    \033[31m○\033[0m Backend    \033[2mnot running\033[0m\n"; fi
	@if lsof -ti :3000 &>/dev/null; then printf "    \033[32m●\033[0m Squawk     pid=$$(lsof -ti :3000 | head -1)  \033[36mhttp://localhost:3000\033[0m\n"; else printf "    \033[31m○\033[0m Squawk     \033[2mnot running\033[0m\n"; fi
	@if lsof -ti :3001 &>/dev/null; then printf "    \033[32m●\033[0m Tower      pid=$$(lsof -ti :3001 | head -1)  \033[36mhttp://localhost:3001\033[0m\n"; else printf "    \033[31m○\033[0m Tower      \033[2mnot running\033[0m\n"; fi
	@if lsof -ti :3002 &>/dev/null; then printf "    \033[32m●\033[0m Hangar     pid=$$(lsof -ti :3002 | head -1)  \033[36mhttp://localhost:3002\033[0m\n"; else printf "    \033[31m○\033[0m Hangar     \033[2mnot running\033[0m\n"; fi
	@printf "\n"
	@printf "  \033[1mURLs\033[0m\n"
	@printf "    Squawk       \033[36mhttp://localhost:3000\033[0m\n"
	@printf "    Tower        \033[36mhttp://localhost:3001\033[0m\n"
	@printf "    Hangar       \033[36mhttp://localhost:3002\033[0m\n"
	@printf "    Backend API  \033[36mhttp://localhost:$(BACKEND_PORT)\033[0m\n"
	@printf "    API Docs     \033[36mhttp://localhost:$(BACKEND_PORT)/docs\033[0m\n"
	@printf "    Health       \033[36mhttp://localhost:$(BACKEND_PORT)/health\033[0m  ·  \033[36m/health/ready\033[0m\n"
	@printf "    Keycloak     \033[36mhttp://localhost:8180\033[0m  \033[2m(if running)\033[0m\n"
	@printf "    Traefik      \033[36mhttp://localhost:8081\033[0m  \033[2m(make up-full only)\033[0m\n"
	@printf "\n"
	@printf "  \033[1mDatabase\033[0m\n"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T postgres psql -U horus -d horus_db -tAc \
		"SELECT 'tables: ' || count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" 2>/dev/null \
		| sed 's/^/    /' || printf "    \033[2mPostgreSQL not reachable\033[0m\n"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T postgres psql -U horus -d horus_db -tAc \
		"SELECT '  users=' || (SELECT count(*) FROM users) || '  orgs=' || (SELECT count(*) FROM organizations) || '  scenarios=' || (SELECT count(*) FROM scenarios) || '  sessions=' || (SELECT count(*) FROM training_sessions)" 2>/dev/null \
		| sed 's/^/    /' || true
	@printf "\n"
	@printf "  \033[1mOllama\033[0m\n"
	@curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; models=json.load(sys.stdin).get('models',[]); [print(f'    \033[32m●\033[0m {m[\"name\"]}') for m in models] or print('    \033[33m!\033[0m no models pulled — run make ollama-pull')" 2>/dev/null || printf "    \033[2mOllama not reachable\033[0m\n"
	@printf "\n"
	@printf "  \033[1mVersions\033[0m\n"
	@printf "    Python   %s\n" "$$(python3 --version 2>/dev/null | cut -d' ' -f2 || echo 'not found')"
	@printf "    Node     %s\n" "$$(node --version 2>/dev/null || echo 'not found')"
	@printf "    pnpm     %s\n" "$$(pnpm --version 2>/dev/null || echo 'not found')"
	@printf "    uv       %s\n" "$$(uv --version 2>/dev/null | cut -d' ' -f2 || echo 'not found')"
	@printf "    Docker   %s\n" "$$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo 'not found')"
	@printf "\n"

.PHONY: health
health: ## Check backend liveness (/health) and readiness (/health/ready)
	@echo "$(CYAN)Checking health...$(RESET)"
	@curl -sf http://localhost:$(BACKEND_PORT)/health 2>/dev/null | grep -q horus-atc-api \
		|| { echo "$(RED)✘$(RESET) Horus backend not responding on port $(BACKEND_PORT)"; exit 1; }
	@curl -s http://localhost:$(BACKEND_PORT)/health/ready | python3 -m json.tool
	@curl -sf http://localhost:$(BACKEND_PORT)/health/ready >/dev/null \
		&& echo "$(GREEN)✓$(RESET) Backend healthy and ready" \
		|| { echo "$(YELLOW)!$(RESET) Backend is up but not ready — see the services above"; exit 1; }

.PHONY: ollama-pull
ollama-pull: ## Pull the chat + embedding models into Ollama (container, or host with OLLAMA_HOST=1)
	@echo "$(CYAN)Pulling $(OLLAMA_MODEL) and $(OLLAMA_EMBED_MODEL)...$(RESET)"
ifeq ($(OLLAMA_HOST),1)
	@ollama pull $(OLLAMA_MODEL)
	@ollama pull $(OLLAMA_EMBED_MODEL)
else
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T ollama ollama pull $(OLLAMA_MODEL)
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec -T ollama ollama pull $(OLLAMA_EMBED_MODEL)
endif
	@echo "$(GREEN)✓$(RESET) Models ready"

.PHONY: clean
clean: ## Remove caches and build output (keeps deps, .env and Docker volumes)
	@echo "$(BOLD)Cleaning...$(RESET)"
	@find $(BACKEND_DIR) -path $(BACKEND_DIR)/.venv -prune -o -type d \
		\( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(BACKEND_DIR)/.coverage $(BACKEND_DIR)/htmlcov
	@rm -rf $(FRONTEND_DIR)/.nuxt $(FRONTEND_DIR)/.output $(FRONTEND_DIR)/.turbo $(FRONTEND_DIR)/node_modules/.vite
	@rm -rf $(FRONTEND_DIR)/apps/*/.output $(FRONTEND_DIR)/apps/*/.turbo
	@echo "$(GREEN)✓$(RESET) Cleaned build artifacts and caches"
