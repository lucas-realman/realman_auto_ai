#!/usr/bin/env bash
# ============================================================
# check_vllm.sh — Health check for a running vLLM server
#
# Usage:
#   bash scripts/check_vllm.sh              # defaults: localhost:8000
#   bash scripts/check_vllm.sh HOST PORT    # custom host/port
#
# Exit codes:
#   0  — vLLM is running and /v1/models returns at least one model
#   1  — vLLM is not reachable or unhealthy
#
# Acceptance:
#   curl localhost:8000/v1/models → returns model name
# ============================================================
set -euo pipefail

HOST="${1:-localhost}"
PORT="${2:-${VLLM_PORT:-8000}}"
URL="http://${HOST}:${PORT}/v1/models"

echo "=========================================="
echo "  vLLM Health Check"
echo "=========================================="
echo "  Endpoint: ${URL}"
echo ""

# --- 1. Connectivity check ---
RESPONSE_FILE=$(mktemp /tmp/vllm_health_XXXXXX.json)
trap 'rm -f "${RESPONSE_FILE}"' EXIT

if ! curl -sf --max-time 10 "${URL}" -o "${RESPONSE_FILE}"; then
    echo "[ERROR] Cannot reach vLLM at ${URL}"
    echo "        Is the server running?"
    echo "        Start with:  bash scripts/start_vllm.sh --daemon"
    exit 1
fi

echo "[OK] vLLM responded."
echo ""

# --- 2. Parse model list ---
echo "--- Models ---"
python3 -c "
import json, sys
with open('${RESPONSE_FILE}') as f:
    data = json.load(f)
models = data.get('data', [])
if not models:
    print('[ERROR] No models loaded.')
    sys.exit(1)
for m in models:
    print(f\"  {m.get('id', 'unknown')}\")
print()
print(f'[OK] {len(models)} model(s) loaded.')
"
STATUS=$?

if [ "${STATUS}" -ne 0 ]; then
    echo "[ERROR] vLLM responded but no models are loaded."
    exit 1
fi

echo ""
echo "=========================================="
echo "  vLLM Health Check PASSED"
echo "=========================================="
exit 0
