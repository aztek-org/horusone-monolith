#!/usr/bin/env bash
# =============================================================================
# gen-lan-certs.sh — locally-trusted TLS cert for the LAN/self-hosted stack
#
# Browsers only expose crypto.subtle (PKCE sign-in) and getUserMedia (voice) in
# a *secure context*: HTTPS, or localhost. Serving Horus over plain HTTP on a
# LAN address silently disables both (#73). This script mints a certificate for
# the LAN hostnames with mkcert's local CA so Traefik can terminate TLS with a
# cert your devices already trust.
#
# Usage:
#   ./scripts/gen-lan-certs.sh                     # LAN_HOSTNAME (default horus.lan)
#   ./scripts/gen-lan-certs.sh --host 192.168.1.50
#   ./scripts/gen-lan-certs.sh --host horus.home
#   ./scripts/gen-lan-certs.sh --force             # overwrite an existing cert
#
# Output: docker/certs/lan.crt + docker/certs/lan.key, consumed by
# docker-compose.lan.yml. Every client device must trust mkcert's root CA
# (`mkcert -CAROOT` → rootCA.pem) or browsers will still warn and refuse the
# secure-context APIs.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="${PROJECT_DIR}/docker/certs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

usage() {
  cat <<EOF
Usage: $0 [--host <hostname>] [--force]

Options:
  --host <hostname>  LAN hostname or IP the app is served on
                     (default: \$LAN_HOSTNAME or horus.lan)
  --force            Overwrite an existing certificate
  -h, --help         Show this help message

Also covers api.<host>, auth.<host>, app.<host>, localhost, 127.0.0.1 and ::1.
EOF
}

HOST="${LAN_HOSTNAME:-horus.lan}"
FORCE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      if [[ $# -lt 2 ]]; then
        error "Missing value for --host"
        usage
        exit 1
      fi
      HOST="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)    error "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

if ! command -v mkcert >/dev/null 2>&1; then
  error "mkcert not found on PATH."
  error "Install it first, e.g.:"
  error "  Linux : sudo apt install libnss3-tools && brew install mkcert  # or the release binary"
  error "  macOS : brew install mkcert"
  error "  Windows: choco install mkcert"
  exit 1
fi

if [[ -f "$CERT_DIR/lan.crt" && "$FORCE" != true ]]; then
  error "A LAN certificate already exists at $CERT_DIR/lan.crt"
  error "Pass --force to overwrite it."
  exit 1
fi

mkdir -p "$CERT_DIR"

NAMES=("$HOST" "api.${HOST}" "auth.${HOST}" "app.${HOST}" "localhost" "127.0.0.1" "::1")

info "Generating LAN certificate for: ${NAMES[*]}"
mkcert -cert-file "$CERT_DIR/lan.crt" -key-file "$CERT_DIR/lan.key" "${NAMES[@]}"

chmod 600 "$CERT_DIR/lan.key" 2>/dev/null || true

echo ""
info "Wrote ${CERT_DIR}/lan.crt and ${CERT_DIR}/lan.key"
warn "Trust mkcert's root CA on every client device: $(mkcert -CAROOT)/rootCA.pem"
warn "Without it browsers warn and keep the page an insecure context."
info "Start the LAN stack with:"
info "  LAN_HOSTNAME=${HOST} docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d"
