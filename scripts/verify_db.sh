#!/usr/bin/env bash
# ==================================================================
# Sirus AI CRM — Quick Database & Cache Verification
# ==================================================================
#
# Lightweight script that checks PostgreSQL and Redis are running
# and the ai_crm database has the expected schema. Matches the
# Sprint 1-2 acceptance criteria:
#
#   psql -c "SELECT 1"   → succeeds
#   redis-cli ping        → PONG
#
# Usage:
#   bash scripts/verify_db.sh
#
# Environment variables (optional — same as init_db.sh):
#   PGUSER      — PostgreSQL user     (default: current user)
#   PGHOST      — PostgreSQL host     (default: localhost)
#   PGPORT      — PostgreSQL port     (default: 5432)
#   DB_NAME     — database name       (default: ai_crm)
#   REDIS_PORT  — Redis listen port   (default: 6379)
#
# Exit codes:
#   0 — All checks passed
#   1 — One or more checks failed
# ==================================================================

set -euo pipefail

# ── Colour helpers ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# ── Configuration (aligned with init_db.sh) ──────────────────────
PGUSER="${PGUSER:-$(whoami)}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
DB_NAME="${DB_NAME:-ai_crm}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# ── Ensure PG 16 binaries are on PATH if installed via brew ──────
if command -v brew &>/dev/null; then
    PG16_BIN="$(brew --prefix postgresql@16 2>/dev/null)/bin"
    if [[ -d "$PG16_BIN" ]]; then
        export PATH="$PG16_BIN:$PATH"
    fi
fi

PASSED=0
FAILED=0

# ── Check helper ─────────────────────────────────────────────────
check() {
    local label="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC}  ${label}"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}❌${NC}  ${label}"
        FAILED=$((FAILED + 1))
    fi
}

# ── Check that expects a specific output ─────────────────────────
check_output() {
    local label="$1"
    local expected="$2"
    shift 2
    local actual
    actual="$("$@" 2>/dev/null)" || true
    actual="$(echo "$actual" | tr -d '[:space:]')"
    if [[ "$actual" == "$expected" ]]; then
        echo -e "  ${GREEN}✅${NC}  ${label}"
        PASSED=$((PASSED + 1))
    else
        echo -e "  ${RED}❌${NC}  ${label}  (expected '${expected}', got '${actual}')"
        FAILED=$((FAILED + 1))
    fi
}

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Sirus AI CRM — Database & Cache Verification"
echo "═══════════════════════════════════════════════════"
echo ""

# ── PostgreSQL connectivity ──────────────────────────────────────
echo "  PostgreSQL (${PGHOST}:${PGPORT}/${DB_NAME})"
echo "  ──────────────────────────────────────"

check "pg_isready" \
    pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER"

check_output "psql SELECT 1" "1" \
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" -tAc "SELECT 1;"

echo ""

# ── Extensions ───────────────────────────────────────────────────
echo "  Extensions"
echo "  ──────────────────────────────────────"

check_output "uuid-ossp extension" "1" \
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" \
         -tAc "SELECT 1 FROM pg_extension WHERE extname='uuid-ossp';"

check_output "pgvector (vector) extension" "1" \
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" \
         -tAc "SELECT 1 FROM pg_extension WHERE extname='vector';"

echo ""

# ── Core tables ──────────────────────────────────────────────────
echo "  Core Tables"
echo "  ──────────────────────────────────────"

for table in users leads customers contacts opportunities activities audit_log agent_log; do
    check_output "table '${table}'" "1" \
        psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" \
             -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='${table}';"
done

echo ""

# ── Triggers ─────────────────────────────────────────────────────
echo "  Triggers"
echo "  ──────────────────────────────────────"

check_output "trigger function update_updated_at()" "1" \
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" \
         -tAc "SELECT 1 FROM pg_proc WHERE proname='update_updated_at';"

for pair in "trg_leads_updated:leads" "trg_customers_updated:customers" \
            "trg_contacts_updated:contacts" "trg_opportunities_updated:opportunities" \
            "trg_users_updated:users"; do
    trigger="${pair%%:*}"
    tbl="${pair##*:}"
    check_output "trigger ${trigger} on ${tbl}" "1" \
        psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" \
             -tAc "SELECT 1 FROM information_schema.triggers WHERE trigger_name='${trigger}' AND event_object_table='${tbl}';"
done

echo ""

# ── Redis ────────────────────────────────────────────────────────
echo "  Redis (${REDIS_HOST}:${REDIS_PORT})"
echo "  ──────────────────────────────────────"

check_output "redis-cli ping → PONG" "PONG" \
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping

echo ""

# ── Summary ──────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}All ${PASSED} checks passed ✅${NC}"
else
    echo -e "  ${GREEN}Passed: ${PASSED}${NC}  |  ${RED}Failed: ${FAILED}${NC}"
fi
echo "═══════════════════════════════════════════════════"
echo ""

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
exit 0
