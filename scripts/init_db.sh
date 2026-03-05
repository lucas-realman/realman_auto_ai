#!/usr/bin/env bash
# ==============================================================
# Sirus AI CRM — Database & Cache Initialisation (macOS / Homebrew)
#
# Installs PostgreSQL 16, pgvector, and Redis 7 via Homebrew,
# creates the ``ai_crm`` database, loads extensions (uuid-ossp,
# vector) and applies the canonical schema from
# ``contracts/db-schema.sql``.
#
# Usage:
#   bash scripts/init_db.sh          # full install + schema
#   bash scripts/init_db.sh --skip-install   # schema only
#
# Environment variables (all optional):
#   PGUSER      — PostgreSQL superuser   (default: current user)
#   PGHOST      — PostgreSQL host        (default: localhost)
#   PGPORT      — PostgreSQL port        (default: 5432)
#   DB_NAME     — target database name   (default: ai_crm)
#   REDIS_PORT  — Redis listen port      (default: 6379)
#
# Exit codes:
#   0  success
#   1  pre-flight check failed (not macOS, brew missing, …)
#   2  installation error
#   3  database / schema error
# ==============================================================

set -euo pipefail

# ── colour helpers ────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$*"; exit "${2:-1}"; }

# ── defaults ──────────────────────────────────────────────────
PGUSER="${PGUSER:-$(whoami)}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
DB_NAME="${DB_NAME:-ai_crm}"
REDIS_PORT="${REDIS_PORT:-6379}"
SKIP_INSTALL=false

# ── arg parsing ───────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --skip-install) SKIP_INSTALL=true ;;
        --help|-h)
            head -n 22 "$0" | tail -n +2 | sed 's/^# \?//'
            exit 0
            ;;
        *) warn "Unknown argument: $arg" ;;
    esac
done

# ── pre-flight checks ────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    fail "This script is designed for macOS.  Detected: $(uname)" 1
fi

if ! command -v brew &>/dev/null; then
    fail "Homebrew is not installed.  Visit https://brew.sh" 1
fi

SCHEMA_FILE="$(cd "$(dirname "$0")/.." && pwd)/contracts/db-schema.sql"
if [[ ! -f "$SCHEMA_FILE" ]]; then
    fail "Schema file not found: $SCHEMA_FILE" 1
fi

# ==============================================================
# 1. Install services via Homebrew
# ==============================================================
if [[ "$SKIP_INSTALL" == false ]]; then
    info "Updating Homebrew…"
    brew update || warn "brew update returned non-zero (continuing)"

    # ── PostgreSQL 16 ──
    if brew list postgresql@16 &>/dev/null; then
        info "postgresql@16 is already installed."
    else
        info "Installing postgresql@16…"
        brew install postgresql@16 || fail "Failed to install postgresql@16" 2
    fi

    # Make sure PG 16 binaries are on PATH for this session
    PG16_BIN="$(brew --prefix postgresql@16)/bin"
    if [[ -d "$PG16_BIN" ]]; then
        export PATH="$PG16_BIN:$PATH"
    fi

    # ── pgvector ──
    if brew list pgvector &>/dev/null; then
        info "pgvector is already installed."
    else
        info "Installing pgvector…"
        brew install pgvector || fail "Failed to install pgvector" 2
    fi

    # ── Redis 7 ──
    if brew list redis &>/dev/null; then
        info "Redis is already installed."
    else
        info "Installing redis…"
        brew install redis || fail "Failed to install redis" 2
    fi

    # ── Start services ──
    info "Starting PostgreSQL 16 service…"
    brew services start postgresql@16 || warn "postgresql@16 service may already be running"
    # Give PG a moment to accept connections
    sleep 2

    info "Starting Redis service…"
    brew services start redis || warn "Redis service may already be running"
    sleep 1
else
    info "Skipping installation (--skip-install)."
    # Still ensure PG 16 binaries are on PATH
    PG16_BIN="$(brew --prefix postgresql@16 2>/dev/null)/bin"
    if [[ -d "$PG16_BIN" ]]; then
        export PATH="$PG16_BIN:$PATH"
    fi
fi

# ==============================================================
# 2. Verify connectivity
# ==============================================================
info "Verifying PostgreSQL connectivity…"
if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" &>/dev/null; then
    fail "PostgreSQL is not accepting connections on ${PGHOST}:${PGPORT}" 3
fi
info "PostgreSQL is ready."

info "Verifying Redis connectivity…"
if ! redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q "PONG"; then
    fail "Redis did not respond to PING on port ${REDIS_PORT}" 3
fi
info "Redis is ready."

# ==============================================================
# 3. Create database & apply schema
# ==============================================================

# Helper: run psql against the target database
run_psql_db() {
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" "$@"
}

# Helper: run psql against the default maintenance database
run_psql_default() {
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres "$@"
}

# Create database if it does not exist
if run_psql_default -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null | grep -q 1; then
    info "Database '${DB_NAME}' already exists."
else
    info "Creating database '${DB_NAME}'…"
    run_psql_default -c "CREATE DATABASE ${DB_NAME};" || fail "Could not create database '${DB_NAME}'" 3
    info "Database '${DB_NAME}' created."
fi

# Enable extensions inside the target database
info "Enabling uuid-ossp extension…"
run_psql_db -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' || fail "Failed to enable uuid-ossp" 3

info "Enabling pgvector extension…"
run_psql_db -c 'CREATE EXTENSION IF NOT EXISTS "vector";' || fail "Failed to enable pgvector (vector)" 3

# Apply schema
info "Applying schema from ${SCHEMA_FILE}…"
run_psql_db -f "$SCHEMA_FILE" || fail "Schema application failed" 3
info "Schema applied successfully."

# ==============================================================
# 4. Quick smoke test
# ==============================================================
info "Running smoke tests…"

RESULT=$(run_psql_db -tAc "SELECT 1;" 2>/dev/null)
if [[ "$RESULT" == "1" ]]; then
    info "✓ psql SELECT 1 — OK"
else
    fail "psql SELECT 1 returned unexpected result: ${RESULT}" 3
fi

TABLE_COUNT=$(run_psql_db -tAc "
    SELECT count(*)
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';
" 2>/dev/null)
info "✓ Tables found in public schema: ${TABLE_COUNT}"

REDIS_PONG=$(redis-cli -p "$REDIS_PORT" ping 2>/dev/null)
if [[ "$REDIS_PONG" == "PONG" ]]; then
    info "✓ redis-cli ping — PONG"
else
    fail "redis-cli ping did not return PONG" 3
fi

# ==============================================================
# Done
# ==============================================================
echo ""
info "========================================="
info " ✅  Initialisation complete!"
info "    PostgreSQL 16  : ${PGHOST}:${PGPORT}/${DB_NAME}"
info "    pgvector       : enabled"
info "    Redis 7        : localhost:${REDIS_PORT}"
info "========================================="
echo ""
info "Next steps:"
echo "  1. Verify: bash scripts/check_db.sh"
echo "  2. Run tests: pytest tests/test_init_db.py -v"
echo ""
exit 0
