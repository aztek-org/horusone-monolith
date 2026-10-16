#!/usr/bin/env bash
# =============================================================================
# backup.sh — PostgreSQL backup for Horus MVP
#
# Dumps horus_db and keycloak_db from the running postgres container, compresses
# with gzip, encrypts with age (unless --no-encrypt), optionally uploads the
# result to an rclone remote, and prunes old local and remote backups.
#
# Usage:
#   ./scripts/backup.sh                     # Encrypt; upload if configured
#   ./scripts/backup.sh --db horus_db       # Backup only horus_db
#   ./scripts/backup.sh --db keycloak_db    # Backup only keycloak_db
#   ./scripts/backup.sh --no-encrypt        # Plain .sql.gz (local/CI use only)
#   ./scripts/backup.sh --require-offsite   # Fail if no rclone remote is set
#
# Environment (see .env.prod.example):
#   BACKUP_AGE_RECIPIENT          age recipient (age1...) or a recipients file.
#                                 Required unless --no-encrypt. The matching
#                                 private key must NOT live on this host.
#   BACKUP_RCLONE_REMOTE          rclone target, e.g. horus-backups:horus-db.
#                                 Empty means local-only.
#   BACKUP_LOCAL_RETENTION_DAYS   Local prune window (default 7).
#   BACKUP_REMOTE_RETENTION_DAYS  Offsite prune window (default 30).
#   BACKUP_AGE_BIN / BACKUP_RCLONE_BIN   Override the binaries (used by tests).
#
# Backups are written to ./backups/ as <db>_<ts>.sql.gz.age (or .sql.gz when
# --no-encrypt) with a sibling .sha256 checksum.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
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
Usage: $0 [--db <database>] [--no-encrypt] [--require-offsite]

Options:
  --db <database>    Backup only one database (horus_db | keycloak_db)
  --no-encrypt       Write plain .sql.gz backups (local/CI use only)
  --require-offsite  Fail unless BACKUP_RCLONE_REMOTE is set
  -h, --help         Show this help message

Environment:
  BACKUP_AGE_RECIPIENT          age recipient or recipients file (encryption)
  BACKUP_RCLONE_REMOTE          rclone remote, e.g. horus-backups:horus-db
  BACKUP_LOCAL_RETENTION_DAYS   default 7
  BACKUP_REMOTE_RETENTION_DAYS  default 30
EOF
}

# --- Parse arguments -------------------------------------------------------
TARGET_DB=""
ENCRYPT=true
REQUIRE_OFFSITE=false
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
    --no-encrypt)
      ENCRYPT=false
      shift
      ;;
    --require-offsite)
      REQUIRE_OFFSITE=true
      shift
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

# --- Resolve tooling & policy ---------------------------------------------
AGE_BIN="${BACKUP_AGE_BIN:-age}"
RCLONE_BIN="${BACKUP_RCLONE_BIN:-rclone}"
AGE_RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"
RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
LOCAL_RETENTION_DAYS="${BACKUP_LOCAL_RETENTION_DAYS:-7}"
REMOTE_RETENTION_DAYS="${BACKUP_REMOTE_RETENTION_DAYS:-30}"

AGE_ARGS=()
if $ENCRYPT; then
  if [[ -z "$AGE_RECIPIENT" ]]; then
    error "BACKUP_AGE_RECIPIENT is not set."
    error "Set it to an age public key (age1...) or a recipients file, or pass --no-encrypt."
    exit 1
  fi
  if ! command -v "$AGE_BIN" >/dev/null 2>&1; then
    error "$AGE_BIN not found on PATH. Install age, or pass --no-encrypt."
    exit 1
  fi
  if [[ -f "$AGE_RECIPIENT" ]]; then
    AGE_ARGS=(-R "$AGE_RECIPIENT")
  else
    AGE_ARGS=(-r "$AGE_RECIPIENT")
  fi
fi

if [[ -n "$RCLONE_REMOTE" ]]; then
  if ! command -v "$RCLONE_BIN" >/dev/null 2>&1; then
    error "$RCLONE_BIN not found on PATH but BACKUP_RCLONE_REMOTE is set."
    exit 1
  fi
elif $REQUIRE_OFFSITE; then
  error "--require-offsite was given but BACKUP_RCLONE_REMOTE is not set."
  exit 1
fi

# --- Pre-flight checks -----------------------------------------------------
cd "$PROJECT_DIR"

if ! $COMPOSE_CMD ps postgres --status running 2>/dev/null | grep -q "running"; then
  error "PostgreSQL container is not running. Start the stack first."
  exit 1
fi

mkdir -p "$BACKUP_DIR"

checksum() {
  local name="$1"
  ( cd "$BACKUP_DIR" && { sha256sum "$name" 2>/dev/null || shasum -a 256 "$name"; } > "${name}.sha256" )
}

upload_offsite() {
  local src="$1" name
  name="$(basename "$src")"
  "$RCLONE_BIN" copyto "$src" "${RCLONE_REMOTE}/${name}"
  "$RCLONE_BIN" check "$src" "${RCLONE_REMOTE}/${name}"
}

# --- Backup each database --------------------------------------------------
SUFFIX=".sql.gz"
if $ENCRYPT; then
  SUFFIX=".sql.gz.age"
fi

BACKED_UP=()
TOTAL_SIZE=0

for DB in "${DATABASES[@]}"; do
  DUMP_USER="horus"
  if [[ "$DB" == "keycloak_db" ]]; then
    DUMP_USER="keycloak"
  fi

  FILENAME="${DB}_${TIMESTAMP}${SUFFIX}"
  FILEPATH="${BACKUP_DIR}/${FILENAME}"

  info "Backing up ${DB} → ${FILENAME} ..."

  if $ENCRYPT; then
    $COMPOSE_CMD exec -T postgres pg_dump \
      -U "$DUMP_USER" \
      -d "$DB" \
      --no-owner \
      --no-privileges \
      --format=plain \
      | gzip \
      | "$AGE_BIN" "${AGE_ARGS[@]}" > "$FILEPATH"
  else
    $COMPOSE_CMD exec -T postgres pg_dump \
      -U "$DUMP_USER" \
      -d "$DB" \
      --no-owner \
      --no-privileges \
      --format=plain \
      | gzip > "$FILEPATH"
  fi

  checksum "$FILENAME"

  FILE_SIZE=$(stat --printf="%s" "$FILEPATH" 2>/dev/null || stat -f%z "$FILEPATH" 2>/dev/null)
  TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
  BACKED_UP+=("${FILENAME} ($(numfmt --to=iec "$FILE_SIZE" 2>/dev/null || echo "${FILE_SIZE}B"))")

  if [[ -n "$RCLONE_REMOTE" ]]; then
    info "  → Uploading ${FILENAME} to ${RCLONE_REMOTE} ..."
    upload_offsite "$FILEPATH"
    upload_offsite "${FILEPATH}.sha256"
  fi

  info "  ✓ ${DB} backed up successfully"
done

# --- Prune old local backups ------------------------------------------------
info "Pruning local backups older than ${LOCAL_RETENTION_DAYS} days ..."
PRUNED=0
while IFS= read -r -d '' old_file; do
  rm -f "$old_file"
  PRUNED=$((PRUNED + 1))
  warn "  Deleted: $(basename "$old_file")"
done < <(find "$BACKUP_DIR" -type f \
  \( -name "*.sql.gz" -o -name "*.sql.gz.age" -o -name "*.sha256" \) \
  -mtime +"$LOCAL_RETENTION_DAYS" -print0 2>/dev/null)

# --- Prune old offsite backups ----------------------------------------------
REMOTE_PRUNED="n/a"
if [[ -n "$RCLONE_REMOTE" ]]; then
  info "Pruning offsite backups older than ${REMOTE_RETENTION_DAYS} days at ${RCLONE_REMOTE} ..."
  "$RCLONE_BIN" delete --min-age "${REMOTE_RETENTION_DAYS}d" "$RCLONE_REMOTE"
  REMOTE_PRUNED=">${REMOTE_RETENTION_DAYS}d"
fi

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
echo "  Encryption : $(if $ENCRYPT; then echo "age (${AGE_RECIPIENT})"; else echo "NONE (plaintext)"; fi)"
echo "  Offsite    : $(if [[ -n "$RCLONE_REMOTE" ]]; then echo "${RCLONE_REMOTE}"; else echo "local only"; fi)"
echo "  Pruned     : ${PRUNED} local (${REMOTE_PRUNED} remote)"
echo "═══════════════════════════════════════════════════════════"
