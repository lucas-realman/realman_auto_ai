#!/usr/bin/env bash
# ============================================================
# stop_vllm.sh — Gracefully stop the vLLM inference server
#
# Usage:
#   bash scripts/stop_vllm.sh
#
# This script:
#   1. Reads the PID from .vllm.pid
#   2. Sends SIGTERM for graceful shutdown
#   3. Waits up to 30s, then SIGKILL if needed
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
PID_FILE="${PROJECT_ROOT}/.vllm.pid"
TIMEOUT=30

echo "=========================================="
echo "  Stopping vLLM Server"
echo "=========================================="

if [ ! -f "${PID_FILE}" ]; then
    echo "[WARN] PID file not found at ${PID_FILE}."
    echo "       vLLM may not be running (or was started in foreground)."

    # Try to find vLLM process anyway
    VLLM_PIDS=$(pgrep -f "vllm.entrypoints.openai.api_server" || true)
    if [ -n "${VLLM_PIDS}" ]; then
        echo "[INFO] Found vLLM process(es): ${VLLM_PIDS}"
        echo "[INFO] Sending SIGTERM ..."
        echo "${VLLM_PIDS}" | xargs kill -TERM 2>/dev/null || true
        echo "[OK] SIGTERM sent."
    else
        echo "[INFO] No vLLM processes found."
    fi
    exit 0
fi

PID=$(cat "${PID_FILE}")
echo "[INFO] vLLM PID: ${PID}"

if ! kill -0 "${PID}" 2>/dev/null; then
    echo "[INFO] Process ${PID} is not running. Cleaning up PID file."
    rm -f "${PID_FILE}"
    exit 0
fi

# --- Graceful shutdown ---
echo "[INFO] Sending SIGTERM to PID ${PID} ..."
kill -TERM "${PID}" 2>/dev/null || true

WAITED=0
while [ "${WAITED}" -lt "${TIMEOUT}" ]; do
    if ! kill -0 "${PID}" 2>/dev/null; then
        echo "[OK] vLLM stopped gracefully (after ${WAITED}s)."
        rm -f "${PID_FILE}"
        exit 0
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    printf "."
done

echo ""
echo "[WARN] vLLM did not stop within ${TIMEOUT}s. Sending SIGKILL ..."
kill -KILL "${PID}" 2>/dev/null || true
sleep 2

if ! kill -0 "${PID}" 2>/dev/null; then
    echo "[OK] vLLM force-killed."
else
    echo "[ERROR] Failed to kill vLLM (PID ${PID}). Manual intervention required."
    exit 1
fi

rm -f "${PID_FILE}"
echo "[OK] PID file cleaned up."
exit 0
