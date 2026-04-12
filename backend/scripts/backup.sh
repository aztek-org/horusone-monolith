#!/usr/bin/env bash
# =============================================================================
# backup.sh — PostgreSQL backup for Horus MVP
#
# Dumps horus_db and keycloak_db from the running postgres container,
# compresses with gzip, and prunes backups older than 7 days.
#
# Usage:
#   ./scripts/backup.sh                   # Backup both databases
#   ./scripts/backup.sh --db horus_db     # Backup only horus_db
#   ./scripts/backup.sh --db keycloak_db  # Backup only keycloak_db
#
# Backups are saved to ./backups/ with timestamped filenames.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS=7
COMPOSE_CMD="docker compose"

# --- Colors ----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
  cat <<EOF
Usage: $0 [--db <database>]

Options:
  --db <database>  Backup only one database (horus_db | keycloak_db)
  -h, --help       Show this help message
EOF
}

# --- Parse arguments -------------------------------------------------------
TARGET_DB=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)
      if [[ $# -lt 2 ]]; then
        error "Missing value for --db"
        usage
        exit 1
      fi
      TARGET_DB="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)    error "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -n "$TARGET_DB" ]] && [[ "$TARGET_DB" != "horus_db" ]] && [[ "$TARGET_DB" != "keycloak_db" ]]; then
  error "Invalid --db value: $TARGET_DB"
  usage
  exit 1
fi

# Determine which databases to back up
if [[ -n "$TARGET_DB" ]]; then
  DATABASES=("$TARGET_DB")
else
  DATABASES=("horus_db" "keycloak_db")
fi

# --- Pre-flight checks -----------------------------------------------------
cd "$PROJECT_DIR"

if ! $COMPOSE_CMD ps postgres --status running 2>/dev/null | grep -q "running"; then
  error "PostgreSQL container is not running. Start the stack first."
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# --- Backup each database --------------------------------------------------
BACKED_UP=()
TOTAL_SIZE=0

for DB in "${DATABASES[@]}"; do
  DUMP_USER="horus"
  if [[ "$DB" == "keycloak_db" ]]; then
    DUMP_USER="keycloak"
  fi

  FILENAME="${DB}_${TIMESTAMP}.sql.gz"
  FILEPATH="${BACKUP_DIR}/${FILENAME}"

  info "Backing up ${DB} → ${FILENAME} ..."

  $COMPOSE_CMD exec -T postgres pg_dump \
    -U "$DUMP_USER" \
    -d "$DB" \
    --no-owner \
    --no-privileges \
    --format=plain \
    | gzip > "$FILEPATH"

  FILE_SIZE=$(stat --printf="%s" "$FILEPATH" 2>/dev/null || stat -f%z "$FILEPATH" 2>/dev/null)
  TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
  BACKED_UP+=("$FILENAME ($(numfmt --to=iec "$FILE_SIZE" 2>/dev/null || echo "${FILE_SIZE}B"))")

  info "  ✓ ${DB} backed up successfully"
done

# --- Prune old backups ------------------------------------------------------
info "Pruning backups older than ${RETENTION_DAYS} days ..."
PRUNED=0
while IFS= read -r -d '' old_file; do
  rm -f "$old_file"
  PRUNED=$((PRUNED + 1))
  warn "  Deleted: $(basename "$old_file")"
done < <(find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

# --- Summary ----------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════════════════════"
info "Backup Summary — ${TIMESTAMP}"
echo "═══════════════════════════════════════════════════════════"
for entry in "${BACKED_UP[@]}"; do
  echo "  • ${entry}"
done
echo "  Total size : $(numfmt --to=iec "$TOTAL_SIZE" 2>/dev/null || echo "${TOTAL_SIZE}B")"
echo "  Location   : ${BACKUP_DIR}/"
echo "  Pruned     : ${PRUNED} old backup(s)"
echo "═══════════════════════════════════════════════════════════"
