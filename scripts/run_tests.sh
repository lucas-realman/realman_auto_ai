#!/usr/bin/env bash
# ============================================================
# run_tests.sh — Pull latest code and run pytest
# ============================================================
# This script is designed to be called by the post-receive hook
# on the orchestrator machine. It can also be run manually.
#
# Usage:
#   bash scripts/run_tests.sh [OPTIONS]
#
# Options:
#   --project-dir DIR    Project directory (default: script's repo root)
#   --no-pull            Skip git pull (useful for local testing)
#   --verbose            Run pytest in verbose mode
#   --report FILE        Write JUnit XML report to FILE
#
# Exit codes:
#   0  — All tests passed
#   1  — Tests failed
#   2  — Environment error (missing deps, bad directory, etc.)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Defaults ──
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DO_PULL=true
VERBOSE=false
REPORT_FILE=""

# ── Parse arguments ──
while [ $# -gt 0 ]; do
    case "$1" in
        --project-dir) PROJECT_DIR="$2"; shift 2 ;;
        --no-pull)     DO_PULL=false; shift ;;
        --verbose)     VERBOSE=true; shift ;;
        --report)      REPORT_FILE="$2"; shift 2 ;;
        -h|--help)
            head -20 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 2 ;;
    esac
done

# ── Logging ──
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# ── Validate project directory ──
if [ ! -d "${PROJECT_DIR}" ]; then
    log "ERROR: Project directory does not exist: ${PROJECT_DIR}"
    exit 2
fi

cd "${PROJECT_DIR}"
log "Working directory: $(pwd)"

# ── Git pull ──
if [ "${DO_PULL}" = true ]; then
    log "Pulling latest code..."
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        git pull --ff-only 2>&1 || {
            log "WARNING: git pull --ff-only failed, trying git fetch"
            git fetch --all 2>&1
        }
        log "Current commit: $(git rev-parse --short HEAD) ($(git log -1 --format='%s'))"
    else
        log "WARNING: Not a git repository, skipping pull"
    fi
fi

# ── Detect Python ──
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    log "ERROR: Python not found"
    exit 2
fi

log "Python: $(${PYTHON} --version 2>&1)"

# ── Install dependencies (if requirements.txt exists) ──
if [ -f "requirements.txt" ]; then
    log "Installing dependencies..."
    ${PYTHON} -m pip install -q -r requirements.txt 2>/dev/null || {
        log "WARNING: pip install failed, continuing anyway"
    }
fi

# ── Check pytest is available ──
if ! ${PYTHON} -m pytest --version &>/dev/null; then
    log "ERROR: pytest not found. Install with: pip install pytest"
    exit 2
fi

log "pytest: $(${PYTHON} -m pytest --version 2>&1)"

# ── Build pytest arguments ──
PYTEST_ARGS=(
    "tests/"
    "--ignore=tests/acceptance"
    "--ignore=tests/test_post_receive.py"
    "--tb=short"
    "--no-header"
    "-q"
)

if [ "${VERBOSE}" = true ]; then
    PYTEST_ARGS+=("-v")
fi

if [ -n "${REPORT_FILE}" ]; then
    PYTEST_ARGS+=("--junitxml=${REPORT_FILE}")
    log "JUnit report will be written to: ${REPORT_FILE}"
fi

# ── Run pytest ──
log "Running: ${PYTHON} -m pytest ${PYTEST_ARGS[*]}"
echo "============================================"

${PYTHON} -m pytest "${PYTEST_ARGS[@]}"
TEST_EXIT=$?

echo "============================================"

if [ ${TEST_EXIT} -eq 0 ]; then
    log "All tests PASSED"
elif [ ${TEST_EXIT} -eq 5 ]; then
    log "No tests collected (exit code 5) — this may be expected"
    TEST_EXIT=0
else
    log "Tests FAILED (exit code: ${TEST_EXIT})"
fi

exit ${TEST_EXIT}
