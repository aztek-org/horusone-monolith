#!/usr/bin/env bash
# =============================================================================
# smoke-first-boot.sh — verify Postgres first-boot initialization really works.
#
# Builds the Postgres image and starts it on a throwaway volume, then asserts
# that the /docker-entrypoint-initdb.d script is executable *inside the image*
# and that it creates keycloak_db. This catches any host/build whose mount or
# permission semantics would silently skip the init script (#20).
#
# Usage: ./scripts/smoke-first-boot.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE="horus-postgres-smoke:local"
CONTAINER="horus-postgres-smoke-$$"
INITDB_PATH="/docker-entrypoint-initdb.d/init-multiple-dbs.sh"
TIMEOUT=60

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

info "Building Postgres image ..."
docker build -q -f "$PROJECT_DIR/docker/Dockerfile.postgres" -t "$IMAGE" "$PROJECT_DIR/docker" >/dev/null

info "Asserting the init script is executable inside the image ..."
docker run --rm --entrypoint test "$IMAGE" -x "$INITDB_PATH" \
  || { error "init script is not executable inside the built image"; exit 1; }

info "Starting throwaway Postgres on a fresh volume ..."
docker run -d --name "$CONTAINER" \
  -e POSTGRES_USER=horus -e POSTGRES_PASSWORD=horus -e POSTGRES_DB=horus_db \
  -e KEYCLOAK_DB_PASSWORD=keycloak "$IMAGE" >/dev/null

info "Waiting for keycloak_db (up to ${TIMEOUT}s) ..."
elapsed=0
until docker exec "$CONTAINER" psql -U horus -d horus_db -tAc \
      "SELECT 1 FROM pg_database WHERE datname='keycloak_db'" 2>/dev/null | grep -q 1; do
  if [[ $elapsed -ge $TIMEOUT ]]; then
    error "keycloak_db was not created within ${TIMEOUT}s"
    docker logs "$CONTAINER" 2>&1 | tail -30
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
info "  ✓ keycloak_db created"

info "Asserting the keycloak role can connect to keycloak_db ..."
docker exec "$CONTAINER" psql -U keycloak -d keycloak_db -tAc "SELECT 1" >/dev/null

info "First-boot smoke check passed."
