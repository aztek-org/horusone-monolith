#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deployment helper for Horus MVP backend
#
# Usage:
#   ./scripts/deploy.sh           # Rebuild & deploy backend only (rolling)
#   ./scripts/deploy.sh --full    # Pull + rebuild all services
#   ./scripts/deploy.sh --skip-migrations  # Skip alembic migrations
#
# Compose files used:
#   docker-compose.yml + docker-compose.prod.yml
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
HEALTH_TIMEOUT=120      # seconds to wait for health check
HEALTH_INTERVAL=5       # seconds between retries

# --- Colors ----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }

# --- Parse arguments -------------------------------------------------------
FULL_DEPLOY=false
SKIP_MIGRATIONS=false
START_TIME=$(date +%s)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)             FULL_DEPLOY=true; shift ;;
    --skip-migrations)  SKIP_MIGRATIONS=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--full] [--skip-migrations]"
      echo ""
      echo "Options:"
      echo "  --full              Pull & rebuild all services (not just backend)"
      echo "  --skip-migrations   Skip running alembic database migrations"
      echo "  -h, --help          Show this help message"
      exit 0
      ;;
    *)  error "Unknown argument: $1"; exit 1 ;;
  esac
done

# --- Pre-flight checks -----------------------------------------------------
cd "$PROJECT_DIR"

if [[ ! -f docker-compose.yml ]]; then
  error "docker-compose.yml not found. Run from the backend/ directory."
  exit 1
fi

if [[ ! -f docker-compose.prod.yml ]]; then
  error "docker-compose.prod.yml not found. Create it first."
  exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
step "Horus MVP — Production Deployment"
echo "  Mode: $(if $FULL_DEPLOY; then echo 'FULL (all services)'; else echo 'Backend only (rolling)'; fi)"
echo "  Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# --- Helper: wait for healthy backend ---------------------------------------
wait_for_health() {
  local elapsed=0
  info "Waiting for backend health check ..."

  while [[ $elapsed -lt $HEALTH_TIMEOUT ]]; do
    # Health check via the container network (backend may not expose ports)
    if $COMPOSE_CMD exec -T backend curl -sf http://localhost:8000/health > /dev/null 2>&1; then
      info "  ✓ Backend healthy after ${elapsed}s"
      return 0
    fi
    sleep "$HEALTH_INTERVAL"
    elapsed=$((elapsed + HEALTH_INTERVAL))
  done

  error "Backend did not become healthy within ${HEALTH_TIMEOUT}s"
  warn "Check logs: $COMPOSE_CMD logs --tail 50 backend"
  return 1
}

# ===========================================================================
# FULL DEPLOY — pull all images, rebuild, restart everything
# ===========================================================================
if $FULL_DEPLOY; then
  step "[1/5] Pulling latest base images ..."
  $COMPOSE_CMD pull

  step "[2/5] Building all services ..."
  $COMPOSE_CMD build --no-cache

  step "[3/5] Starting infrastructure (postgres, redis, ollama, keycloak, traefik) ..."
  $COMPOSE_CMD up -d postgres redis ollama keycloak traefik

  # Wait for postgres to be healthy before migrations
  info "Waiting for PostgreSQL to be healthy ..."
  timeout 60 bash -c "until $COMPOSE_CMD exec -T postgres pg_isready -U horus -d horus_db > /dev/null 2>&1; do sleep 2; done"
  info "  ✓ PostgreSQL ready"

  if ! $SKIP_MIGRATIONS; then
    step "[4/5] Running database migrations ..."
    $COMPOSE_CMD run --rm --no-deps backend alembic upgrade head
    info "  ✓ Migrations complete"
  else
    step "[4/5] Skipping database migrations (--skip-migrations)"
  fi

  step "[5/5] Starting backend ..."
  $COMPOSE_CMD up -d backend

  wait_for_health

# ===========================================================================
# BACKEND-ONLY DEPLOY — rolling update with zero downtime
# ===========================================================================
else
  step "[1/4] Building new backend image ..."
  $COMPOSE_CMD build backend

  if ! $SKIP_MIGRATIONS; then
    step "[2/4] Running database migrations ..."
    $COMPOSE_CMD run --rm --no-deps backend alembic upgrade head
    info "  ✓ Migrations complete"
  else
    step "[2/4] Skipping database migrations (--skip-migrations)"
  fi

  step "[3/4] Rolling update — scaling backend to 2 replicas ..."
  # Scale to 2 so the new container starts before the old one stops
  $COMPOSE_CMD up -d --no-deps --scale backend=2 --no-recreate backend 2>/dev/null || true
  sleep 5

  # Now recreate with scale 1, which replaces the old container
  $COMPOSE_CMD up -d --no-deps --force-recreate --scale backend=1 backend

  step "[4/4] Verifying deployment ..."
  wait_for_health
fi

# --- Summary ----------------------------------------------------------------
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Grab running image digests
BACKEND_IMAGE=$($COMPOSE_CMD images backend --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | head -1 || echo "unknown")

echo ""
echo "═══════════════════════════════════════════════════════════"
info "Deployment Complete"
echo "═══════════════════════════════════════════════════════════"
echo "  Duration   : ${DURATION}s"
echo "  Mode       : $(if $FULL_DEPLOY; then echo 'full'; else echo 'backend-only'; fi)"
echo "  Migrations : $(if $SKIP_MIGRATIONS; then echo 'skipped'; else echo 'applied'; fi)"
echo "  Backend    : ${BACKEND_IMAGE}"
echo ""
echo "  Services:"
$COMPOSE_CMD ps --format "    {{.Name}}\t{{.Status}}" 2>/dev/null || $COMPOSE_CMD ps
echo "═══════════════════════════════════════════════════════════"
