#!/usr/bin/env bash
# =============================================================================
# restore.sh — PostgreSQL restore for Horus MVP
#
# Restores a database from a backup file (.sql, .sql.gz, or an age-encrypted
# .sql.gz.age produced by backup.sh). Auto-detects the target database from the
# filename.
#
# Usage:
#   ./scripts/restore.sh backups/horus_db_20240101_120000.sql.gz
#   ./scripts/restore.sh backups/keycloak_db_20240101_120000.sql.gz
#   ./scripts/restore.sh --db horus_db backups/some-custom-name.sql.gz
#   BACKUP_AGE_IDENTITY=~/.config/age/horus-backup.key \
#     ./scripts/restore.sh backups/horus_db_20240101_120000.sql.gz.age
#
# Environment:
#   BACKUP_AGE_IDENTITY   Path to the age private key (required for .age files)
#   BACKUP_AGE_BIN        Override the age binary (default: age)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_CMD="docker compose"
AGE_BIN="${BACKUP_AGE_BIN:-age}"
AGE_IDENTITY="${BACKUP_AGE_IDENTITY:-}"

# --- Colors ----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
  cat <<EOF
Usage: $0 [--db <database>] <backup-file>

Examples:
  $0 backups/horus_db_20240101_120000.sql.gz
  $0 backups/keycloak_db_20240101_120000.sql.gz
  $0 --db horus_db backups/some-custom-name.sql.gz

Options:
  --db <database>  Force restore target (horus_db | keycloak_db)
  -h, --help       Show this help message

Encrypted (.age) backups require BACKUP_AGE_IDENTITY to point at the private key.
EOF
}

# --- Parse arguments -------------------------------------------------------
FORCE_DB=""
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)
      if [[ $# -lt 2 ]]; then
        error "Missing value for --db"
        usage
        exit 1
      fi
      FORCE_DB="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)   error "Unknown option: $1"; exit 1 ;;
    *)    BACKUP_FILE="$1"; shift ;;
  esac
done

if [[ -z "$BACKUP_FILE" ]]; then
  error "Missing <backup-file> argument."
  usage
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  error "Backup file not found: $BACKUP_FILE"
  exit 1
fi

if [[ -n "$FORCE_DB" ]] && [[ "$FORCE_DB" != "horus_db" ]] && [[ "$FORCE_DB" != "keycloak_db" ]]; then
  error "Invalid --db value: $FORCE_DB"
  usage
  exit 1
fi

# --- Detect target database ------------------------------------------------
BASENAME="$(basename "$BACKUP_FILE")"

if [[ -n "$FORCE_DB" ]]; then
  TARGET_DB="$FORCE_DB"
elif [[ "$BASENAME" == horus_db* ]]; then
  TARGET_DB="horus_db"
elif [[ "$BASENAME" == keycloak_db* ]]; then
  TARGET_DB="keycloak_db"
else
  error "Cannot determine target database from filename: $BASENAME"
  error "Use --db <database> to specify explicitly."
  exit 1
fi

# Determine the correct postgres user for the database
RESTORE_USER="horus"
if [[ "$TARGET_DB" == "keycloak_db" ]]; then
  RESTORE_USER="keycloak"
fi

# --- Detect encryption & compression ---------------------------------------
IS_ENCRYPTED=false
if [[ "$BACKUP_FILE" == *.age ]]; then
  IS_ENCRYPTED=true
fi

IS_GZIPPED=false
if [[ "$BACKUP_FILE" == *.gz || "$BACKUP_FILE" == *.gz.age ]]; then
  IS_GZIPPED=true
fi

# --- Pre-flight checks -----------------------------------------------------
cd "$PROJECT_DIR"

if $IS_ENCRYPTED; then
  if [[ -z "$AGE_IDENTITY" ]]; then
    error "Encrypted backup given but BACKUP_AGE_IDENTITY is not set."
    error "Point it at the age private key, e.g. BACKUP_AGE_IDENTITY=~/.config/age/horus-backup.key"
    exit 1
  fi
  if [[ ! -f "$AGE_IDENTITY" ]]; then
    error "age identity file not found: $AGE_IDENTITY"
    exit 1
  fi
  if ! command -v "$AGE_BIN" >/dev/null 2>&1; then
    error "$AGE_BIN not found on PATH (needed to decrypt $BASENAME)."
    exit 1
  fi
fi

if ! $COMPOSE_CMD ps postgres --status running 2>/dev/null | grep -q "running"; then
  error "PostgreSQL container is not running. Start the stack first."
  exit 1
fi

FILE_SIZE=$(stat --printf="%s" "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)

# --- Confirmation -----------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════════════════════"
warn "DATABASE RESTORE"
echo "═══════════════════════════════════════════════════════════"
echo "  File     : ${BACKUP_FILE}"
echo "  Size     : $(numfmt --to=iec "$FILE_SIZE" 2>/dev/null || echo "${FILE_SIZE}B")"
echo "  Target   : ${TARGET_DB}"
echo "  User     : ${RESTORE_USER}"
echo "  Compress : $(if $IS_GZIPPED; then echo 'gzip'; else echo 'plain SQL'; fi)"
echo "  Encrypt  : $(if $IS_ENCRYPTED; then echo 'age'; else echo 'none'; fi)"
echo "═══════════════════════════════════════════════════════════"
echo ""
warn "⚠  This will DROP and RECREATE the '${TARGET_DB}' database."
warn "⚠  All existing data in '${TARGET_DB}' will be permanently lost."
echo ""

read -r -p "Type 'yes' to proceed: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  info "Restore cancelled."
  exit 0
fi

# --- Restore ----------------------------------------------------------------
info "Dropping and recreating ${TARGET_DB} ..."

# Use the superuser (horus) to drop/create regardless of target DB
$COMPOSE_CMD exec -T postgres psql -U horus -d postgres <<-EOSQL
  -- Terminate existing connections
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();

  DROP DATABASE IF EXISTS ${TARGET_DB};
  CREATE DATABASE ${TARGET_DB} OWNER ${RESTORE_USER};
EOSQL

# Grant schema permissions (needed for PostgreSQL 15+)
$COMPOSE_CMD exec -T postgres psql -U horus -d "${TARGET_DB}" <<-EOSQL
  GRANT ALL ON SCHEMA public TO ${RESTORE_USER};
EOSQL

info "Restoring from backup ..."

stream_backup() {
  if $IS_ENCRYPTED; then
    "$AGE_BIN" -d -i "$AGE_IDENTITY" "$BACKUP_FILE"
  else
    cat "$BACKUP_FILE"
  fi
}

if $IS_GZIPPED; then
  stream_backup | gunzip -c \
    | $COMPOSE_CMD exec -T postgres psql -U "$RESTORE_USER" -d "$TARGET_DB" --quiet
else
  stream_backup \
    | $COMPOSE_CMD exec -T postgres psql -U "$RESTORE_USER" -d "$TARGET_DB" --quiet
fi

# --- Verify -----------------------------------------------------------------
TABLE_COUNT=$($COMPOSE_CMD exec -T postgres psql -U "$RESTORE_USER" -d "$TARGET_DB" -t -A -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")

echo ""
echo "═══════════════════════════════════════════════════════════"
info "Restore Complete"
echo "═══════════════════════════════════════════════════════════"
echo "  Database : ${TARGET_DB}"
echo "  Tables   : ${TABLE_COUNT} tables restored"
echo "  Source   : ${BACKUP_FILE}"
echo "═══════════════════════════════════════════════════════════"
