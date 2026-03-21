# ═══════════════════════════════════════════════════════════════════════════════
# Horus MVP — Project Makefile
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   make              — show available commands
#   make setup        — first-time project setup
#   make up           — start dev infrastructure + backend + frontend
#   make down         — stop everything
#   make info         — show service status and URLs
#
# ═══════════════════════════════════════════════════════════════════════════════

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Config ────────────────────────────────────────────────────────────────────
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod
BACKEND_DIR := backend
FRONTEND_DIR := frontend
UV_RUN := cd $(BACKEND_DIR) && uv run
OLLAMA_MODEL := llama3.2:latest

# Set OLLAMA_HOST=1 to skip the Ollama Docker container and use host-installed Ollama.
#   make up OLLAMA_HOST=1
#   make up-infra OLLAMA_HOST=1
OLLAMA_HOST ?= 0
ifeq ($(OLLAMA_HOST),1)
  INFRA_SERVICES := postgres redis
  OLLAMA_URL := http://host.docker.internal:11434
else
  INFRA_SERVICES := postgres redis ollama
  OLLAMA_URL := http://ollama:11434
endif

# ── Colors ────────────────────────────────────────────────────────────────────
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
DIM := \033[2m
BOLD := \033[1m
RESET := \033[0m

# ══════════════════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: help
help: ## Show this help
	@printf "\n"
	@printf "  \033[1m🛩️  Horus MVP\033[0m — AI-Powered Aviation Training Platform\n"
	@printf "\n"
	@printf "  \033[1mSetup\033[0m\n"
	@printf "    \033[36mmake setup             \033[0m First-time project setup (installs everything)\n"
	@printf "    \033[36mmake install           \033[0m Install all dependencies\n"
	@printf "    \033[36mmake install-backend   \033[0m Install backend Python dependencies\n"
	@printf "    \033[36mmake install-frontend  \033[0m Install frontend Node dependencies\n"
	@printf "\n"
	@printf "  \033[1mDevelopment\033[0m\n"
	@printf "    \033[36mmake up                \033[0m Start dev environment (infra + backend + frontend)\n"
	@printf "    \033[36mmake up OLLAMA_HOST=1   \033[0m Same, but use host-installed Ollama (skip Docker)\n"
	@printf "    \033[36mmake up-infra          \033[0m Start only infrastructure (postgres, redis, ollama)\n"
	@printf "    \033[36mmake up-full           \033[0m Start full stack including Keycloak\n"
	@printf "    \033[36mmake down              \033[0m Stop everything (infra + background processes)\n"
	@printf "    \033[36mmake restart           \033[0m Restart everything\n"
	@printf "    \033[36mmake backend           \033[0m Start backend only (assumes infra running)\n"
	@printf "    \033[36mmake frontend          \033[0m Start frontend only\n"
	@printf "    \033[36mmake logs              \033[0m Show Docker container logs (follow)\n"
	@printf "\n"
	@printf "  \033[1mDatabase\033[0m\n"
	@printf "    \033[36mmake migrate           \033[0m Run database migrations\n"
	@printf "    \033[36mmake migrate-create    \033[0m Create migration (MSG=\"desc\")\n"
	@printf "    \033[36mmake migrate-down      \033[0m Rollback last migration\n"
	@printf "    \033[36mmake migrate-status    \033[0m Show current migration status\n"
	@printf "    \033[36mmake seed              \033[0m Seed database with demo data\n"
	@printf "    \033[36mmake seed-reset        \033[0m Reset and re-seed database\n"
	@printf "    \033[36mmake db-shell          \033[0m Open PostgreSQL shell\n"
	@printf "    \033[36mmake db-reset          \033[0m ⚠ Destroy DB, re-migrate, re-seed\n"
	@printf "\n"
	@printf "  \033[1mTesting & Quality\033[0m\n"
	@printf "    \033[36mmake test              \033[0m Run all tests\n"
	@printf "    \033[36mmake test-backend      \033[0m Run backend tests\n"
	@printf "    \033[36mmake test-frontend     \033[0m Run frontend tests\n"
	@printf "    \033[36mmake test-cov          \033[0m Backend tests with coverage\n"
	@printf "    \033[36mmake lint              \033[0m Lint everything\n"
	@printf "    \033[36mmake format            \033[0m Format everything\n"
	@printf "    \033[36mmake check             \033[0m Run lint + tests (CI-like)\n"
	@printf "    \033[36mmake typecheck         \033[0m Run mypy type checking\n"
	@printf "\n"
	@printf "  \033[1mProduction\033[0m\n"
	@printf "    \033[36mmake prod-up           \033[0m Start production stack\n"
	@printf "    \033[36mmake prod-down         \033[0m Stop production stack\n"
	@printf "    \033[36mmake deploy            \033[0m Deploy backend (rolling update)\n"
	@printf "    \033[36mmake deploy-full       \033[0m Deploy everything (full rebuild)\n"
	@printf "    \033[36mmake backup            \033[0m Backup PostgreSQL databases\n"
	@printf "    \033[36mmake restore           \033[0m Restore DB (FILE=backups/xxx.sql.gz)\n"
	@printf "\n"
	@printf "  \033[1mInfo\033[0m\n"
	@printf "    \033[36mmake info              \033[0m Show project status and URLs\n"
	@printf "    \033[36mmake health            \033[0m Check backend health endpoint\n"
	@printf "    \033[36mmake clean             \033[0m Remove build artifacts and caches\n"
	@printf "    \033[36mmake ollama-pull       \033[0m Pull the default Ollama model\n"
	@printf "\n"

# ══════════════════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: setup
setup: ## First-time project setup (installs everything)
	@echo "$(BOLD)═══ Horus MVP — Setup ═══$(RESET)"
	@./setup.sh
	@echo ""
	@echo "$(BOLD)Running migrations...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d postgres && sleep 5
	@$(UV_RUN) alembic upgrade head
	@echo ""
	@echo "$(BOLD)Seeding database...$(RESET)"
	@$(UV_RUN) python -m scripts.seed
	@echo ""
	@echo "$(GREEN)$(BOLD)✓ Setup complete!$(RESET) Run $(CYAN)make up$(RESET) to start developing."

.PHONY: install
install: install-backend install-frontend ## Install all dependencies

.PHONY: install-backend
install-backend: ## Install backend Python dependencies
	@echo "$(CYAN)Installing backend dependencies...$(RESET)"
	@cd $(BACKEND_DIR) && uv sync --quiet
	@echo "$(GREEN)✓$(RESET) Backend deps installed"

.PHONY: install-frontend
install-frontend: ## Install frontend Node dependencies
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm install --silent
	@echo "$(GREEN)✓$(RESET) Frontend deps installed"

# ══════════════════════════════════════════════════════════════════════════════
# DEVELOPMENT
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: up
up: ## Start dev environment (infra + backend + frontend)
	@echo "$(BOLD)═══ Starting Horus dev environment ═══$(RESET)"
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
	@cd $(BACKEND_DIR) && _n=0; while [ $$_n -lt 30 ]; do \
		$(COMPOSE_DEV) exec -T postgres pg_isready -U horus -q 2>/dev/null && break; \
		_n=$$((_n + 1)); sleep 1; \
	done; \
	if [ $$_n -ge 30 ]; then \
		echo "$(RED)✘ PostgreSQL failed to start within 30s$(RESET)"; \
		echo "  Run $(CYAN)make logs$(RESET) for details"; exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) PostgreSQL ready"
	@echo ""
	@echo "$(CYAN)▸ Running migrations...$(RESET)"
	@$(UV_RUN) alembic upgrade head 2>&1 | tail -2
	@echo ""
	@echo "$(CYAN)▸ Starting backend (port 8000)...$(RESET)"
	@$(UV_RUN) uvicorn app.main:app --reload --port 8000 &>/dev/null &
	@sleep 2
	@echo "$(GREEN)✓$(RESET) Backend started (PID: $$(lsof -ti :8000 2>/dev/null || echo '?'))"
	@echo ""
	@echo "$(CYAN)▸ Starting frontend (port 3000)...$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm dev &>/dev/null &
	@sleep 3
	@echo "$(GREEN)✓$(RESET) Frontend started"
	@echo ""
	@echo "$(GREEN)$(BOLD)═══ Horus is running! ═══$(RESET)"
	@echo ""
	@echo "  $(BOLD)Frontend$(RESET)   → $(CYAN)http://localhost:3000$(RESET)"
	@echo "  $(BOLD)Backend$(RESET)    → $(CYAN)http://localhost:8000$(RESET)"
	@echo "  $(BOLD)API Docs$(RESET)   → $(CYAN)http://localhost:8000/docs$(RESET)"
	@echo "  $(BOLD)Health$(RESET)     → $(CYAN)http://localhost:8000/health$(RESET)"
	@echo ""
	@echo "  $(DIM)Stop with: make down$(RESET)"

.PHONY: up-infra
up-infra: ## Start only infrastructure (postgres, redis, ollama)
	@echo "$(CYAN)Starting infrastructure ($(INFRA_SERVICES))...$(RESET)"
ifeq ($(OLLAMA_HOST),1)
	@echo "  $(YELLOW)▸ Ollama: using host installation$(RESET)"
endif
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d $(INFRA_SERVICES)
	@echo "$(GREEN)✓$(RESET) Infrastructure running"

.PHONY: up-full
up-full: ## Start full stack including Keycloak
	@echo "$(CYAN)Starting full stack with Keycloak...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d
	@echo "$(GREEN)✓$(RESET) Full stack running (Keycloak at http://localhost:8180)"

.PHONY: down
down: ## Stop everything (infra + background processes)
	@echo "$(BOLD)Stopping Horus...$(RESET)"
	@-lsof -ti :8000 2>/dev/null | xargs -r kill 2>/dev/null && echo "$(GREEN)✓$(RESET) Backend stopped" || true
	@-lsof -ti :3000 2>/dev/null | xargs -r kill 2>/dev/null && echo "$(GREEN)✓$(RESET) Frontend stopped" || true
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) down 2>/dev/null
	@echo "$(GREEN)✓$(RESET) Infrastructure stopped"

.PHONY: restart
restart: down up ## Restart everything

.PHONY: backend
backend: ## Start backend only (assumes infra is running)
	@echo "$(CYAN)Starting backend on port 8000...$(RESET)"
	@$(UV_RUN) uvicorn app.main:app --reload --port 8000

.PHONY: frontend
frontend: ## Start frontend only
	@echo "$(CYAN)Starting frontend on port 3000...$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm dev

.PHONY: logs
logs: ## Show Docker container logs (follow)
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) logs -f --tail=50

.PHONY: logs-backend
logs-backend: ## Show backend container logs
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) logs -f --tail=50 backend

# ══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: migrate
migrate: ## Run database migrations
	@echo "$(CYAN)Running migrations...$(RESET)"
	@$(UV_RUN) alembic upgrade head
	@echo "$(GREEN)✓$(RESET) Migrations applied"

.PHONY: migrate-create
migrate-create: ## Create new migration (usage: make migrate-create MSG="add_field")
	@if [ -z "$(MSG)" ]; then echo "$(RED)✘$(RESET) Usage: make migrate-create MSG=\"description\""; exit 1; fi
	@$(UV_RUN) alembic revision --autogenerate -m "$(MSG)"
	@echo "$(GREEN)✓$(RESET) Migration created"

.PHONY: migrate-down
migrate-down: ## Rollback last migration
	@echo "$(YELLOW)⚠ Rolling back last migration...$(RESET)"
	@$(UV_RUN) alembic downgrade -1
	@echo "$(GREEN)✓$(RESET) Rolled back"

.PHONY: migrate-status
migrate-status: ## Show current migration status
	@$(UV_RUN) alembic current

.PHONY: seed
seed: ## Seed database with demo data (idempotent)
	@$(UV_RUN) python -m scripts.seed

.PHONY: seed-reset
seed-reset: ## Reset and re-seed database
	@$(UV_RUN) python -m scripts.seed --reset

.PHONY: db-shell
db-shell: ## Open PostgreSQL shell
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) exec postgres psql -U horus -d horus_db

.PHONY: db-reset
db-reset: ## ⚠ Destroy DB volume, re-migrate, re-seed
	@echo "$(RED)$(BOLD)⚠  This will destroy ALL database data!$(RESET)"
	@read -p "  Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo ""
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) down -v 2>/dev/null || true
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) up -d postgres
	@echo "$(CYAN)Waiting for PostgreSQL...$(RESET)"
	@sleep 5
	@cd $(BACKEND_DIR) && until $(COMPOSE_DEV) exec -T postgres pg_isready -U horus -q 2>/dev/null; do sleep 1; done
	@$(UV_RUN) alembic upgrade head
	@$(UV_RUN) python -m scripts.seed
	@echo "$(GREEN)✓$(RESET) Database reset complete"

# ══════════════════════════════════════════════════════════════════════════════
# TESTING & QUALITY
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: test
test: test-backend test-frontend ## Run all tests

.PHONY: test-backend
test-backend: ## Run backend tests
	@echo "$(BOLD)═══ Backend Tests ═══$(RESET)"
	@$(UV_RUN) pytest tests/ -v

.PHONY: test-frontend
test-frontend: ## Run frontend tests
	@echo "$(BOLD)═══ Frontend Tests ═══$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm test

.PHONY: test-cov
test-cov: ## Run backend tests with coverage
	@$(UV_RUN) pytest tests/ --cov=app --cov-report=term-missing

.PHONY: lint
lint: lint-backend lint-frontend ## Lint everything

.PHONY: lint-backend
lint-backend: ## Lint backend (ruff)
	@echo "$(BOLD)═══ Backend Lint ═══$(RESET)"
	@$(UV_RUN) ruff check app/

.PHONY: lint-frontend
lint-frontend: ## Lint frontend (ESLint)
	@echo "$(BOLD)═══ Frontend Lint ═══$(RESET)"
	@cd $(FRONTEND_DIR) && pnpm lint

.PHONY: format
format: format-backend format-frontend ## Format everything

.PHONY: format-backend
format-backend: ## Format backend (ruff)
	@$(UV_RUN) ruff format app/
	@echo "$(GREEN)✓$(RESET) Backend formatted"

.PHONY: format-frontend
format-frontend: ## Format frontend (Prettier)
	@cd $(FRONTEND_DIR) && pnpm format
	@echo "$(GREEN)✓$(RESET) Frontend formatted"

.PHONY: check
check: lint test ## Run lint + tests (CI-like check)

.PHONY: typecheck
typecheck: ## Run mypy type checking on backend
	@$(UV_RUN) mypy app/

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTION
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: prod-up
prod-up: ## Start production stack
	@echo "$(BOLD)Starting production stack...$(RESET)"
	@cd $(BACKEND_DIR) && $(COMPOSE_PROD) up -d
	@echo "$(GREEN)✓$(RESET) Production running"

.PHONY: prod-down
prod-down: ## Stop production stack
	@cd $(BACKEND_DIR) && $(COMPOSE_PROD) down

.PHONY: deploy
deploy: ## Deploy backend (rolling update)
	@cd $(BACKEND_DIR) && ./scripts/deploy.sh

.PHONY: deploy-full
deploy-full: ## Deploy everything (full rebuild)
	@cd $(BACKEND_DIR) && ./scripts/deploy.sh --full

.PHONY: backup
backup: ## Backup PostgreSQL databases
	@cd $(BACKEND_DIR) && ./scripts/backup.sh

.PHONY: restore
restore: ## Restore database (usage: make restore FILE=backups/xxx.sql.gz)
	@if [ -z "$(FILE)" ]; then echo "$(RED)✘$(RESET) Usage: make restore FILE=backups/filename.sql.gz"; exit 1; fi
	@cd $(BACKEND_DIR) && ./scripts/restore.sh $(FILE)

# ══════════════════════════════════════════════════════════════════════════════
# INFO
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: info
info: ## Show project status, services, and URLs
	@printf "\n"
	@printf "\033[1m═══════════════════════════════════════════════════════════\033[0m\n"
	@printf "\033[1m  🛩️  Horus MVP — Status\033[0m\n"
	@printf "\033[1m═══════════════════════════════════════════════════════════\033[0m\n"
	@printf "\n"
	@printf "  \033[1mDocker Containers\033[0m\n"
	@cd $(BACKEND_DIR) && $(COMPOSE_DEV) ps --format "    {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "    \033[2mNo containers running\033[0m\n"
	@printf "\n"
	@printf "  \033[1mLocal Processes\033[0m\n"
	@if lsof -ti :8000 &>/dev/null; then printf "    \033[32m●\033[0m Backend    pid=$$(lsof -ti :8000 | head -1)  \033[36mhttp://localhost:8000\033[0m\n"; else printf "    \033[31m○\033[0m Backend    \033[2mnot running\033[0m\n"; fi
	@if lsof -ti :3000 &>/dev/null; then printf "    \033[32m●\033[0m Frontend   pid=$$(lsof -ti :3000 | head -1)  \033[36mhttp://localhost:3000\033[0m\n"; else printf "    \033[31m○\033[0m Frontend   \033[2mnot running\033[0m\n"; fi
	@printf "\n"
	@printf "  \033[1mURLs\033[0m\n"
	@printf "    Frontend     \033[36mhttp://localhost:3000\033[0m\n"
	@printf "    Backend API  \033[36mhttp://localhost:8000\033[0m\n"
	@printf "    API Docs     \033[36mhttp://localhost:8000/docs\033[0m\n"
	@printf "    Health       \033[36mhttp://localhost:8000/health\033[0m\n"
	@printf "    Keycloak     \033[36mhttp://localhost:8180\033[0m  \033[2m(if running)\033[0m\n"
	@printf "    Traefik      \033[36mhttp://localhost:8080\033[0m  \033[2m(if running)\033[0m\n"
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
	@curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; models=json.load(sys.stdin).get('models',[]); [print(f'    \033[32m●\033[0m {m[\"name\"]}') for m in models]" 2>/dev/null || printf "    \033[2mOllama not reachable\033[0m\n"
	@printf "\n"
	@printf "  \033[1mVersions\033[0m\n"
	@printf "    Python   %s\n" "$$(python3 --version 2>/dev/null | cut -d' ' -f2 || echo 'not found')"
	@printf "    Node     %s\n" "$$(node --version 2>/dev/null || echo 'not found')"
	@printf "    pnpm     %s\n" "$$(pnpm --version 2>/dev/null || echo 'not found')"
	@printf "    uv       %s\n" "$$(uv --version 2>/dev/null | cut -d' ' -f2 || echo 'not found')"
	@printf "    Docker   %s\n" "$$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',' || echo 'not found')"
	@printf "\n"

.PHONY: health
health: ## Check backend health endpoint
	@echo "$(CYAN)Checking health...$(RESET)"
	@curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null && echo "" && echo "$(GREEN)✓$(RESET) Backend healthy" \
		|| echo "$(RED)✘$(RESET) Backend not responding on port 8000"

.PHONY: clean
clean: ## Remove build artifacts, caches, volumes
	@echo "$(BOLD)Cleaning...$(RESET)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@rm -rf $(BACKEND_DIR)/.coverage $(BACKEND_DIR)/htmlcov 2>/dev/null || true
	@rm -rf $(FRONTEND_DIR)/.nuxt $(FRONTEND_DIR)/.output $(FRONTEND_DIR)/node_modules/.vite 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Cleaned build artifacts and caches"

.PHONY: ollama-pull
ollama-pull: ## Pull the default Ollama model
	@echo "$(CYAN)Pulling $(OLLAMA_MODEL)...$(RESET)"
	@ollama pull $(OLLAMA_MODEL)
	@echo "$(GREEN)✓$(RESET) Model ready"
