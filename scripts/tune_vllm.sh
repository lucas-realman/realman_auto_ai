#!/usr/bin/env bash
# ============================================================
# tune_vllm.sh — Validate vLLM tuning parameters and run benchmark
#
# Usage:
#   bash scripts/tune_vllm.sh              # validate running server
#   bash scripts/tune_vllm.sh --restart    # restart with tuned params + benchmark
#
# This script verifies the Sprint 1-2 tuning requirements:
#   - tensor-parallel-size = 2  (2×RTX 4090)
#   - enable-prefix-caching    (KV cache reuse)
#   - gpu-memory-utilization = 0.85
#
# Acceptance criteria:
#   - TTFT < 2s
#   - Throughput > 20 tok/s
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

BASE_URL="${VLLM_BASE_URL:-http://localhost:8000}"
MODEL="${VLLM_MODEL:-Qwen/Qwen3-30B-A3B}"
RESTART=false

for arg in "$@"; do
    case "${arg}" in
        --restart|-r)
            RESTART=true
            ;;
        --help|-h)
            head -20 "$0" | tail -17
            exit 0
            ;;
    esac
done

echo "=========================================="
echo "  vLLM Tuning Validation"
echo "=========================================="
echo ""

# ── Step 1: GPU check ──
echo "── Step 1: GPU Check ──"
if ! bash "${SCRIPT_DIR}/check_gpu.sh"; then
    echo "[ERROR] GPU check failed. Fix GPU issues first."
    exit 1
fi
echo ""

# ── Step 2: Verify tuning parameters in start script ──
echo "── Step 2: Verify Tuning Parameters ──"
START_SCRIPT="${SCRIPT_DIR}/start_vllm.sh"
PARAM_ERRORS=0

check_param() {
    local param_name="$1"
    local expected="$2"
    local pattern="$3"

    if grep -q "${pattern}" "${START_SCRIPT}"; then
        echo "  [OK] ${param_name} = ${expected}"
    else
        echo "  [FAIL] ${param_name} not set to ${expected}"
        PARAM_ERRORS=$((PARAM_ERRORS + 1))
    fi
}

check_param "tensor-parallel-size" "2" "TP_SIZE.*:-2"
check_param "gpu-memory-utilization" "0.85" "GPU_MEMORY_UTIL.*:-0.85"
check_param "enable-prefix-caching" "enabled" "\-\-enable-prefix-caching"
check_param "max-model-len" "8192" "MAX_MODEL_LEN.*:-8192"
check_param "max-num-seqs" "64" "MAX_NUM_SEQS.*:-64"

if [ "${PARAM_ERRORS}" -gt 0 ]; then
    echo ""
    echo "  [ERROR] ${PARAM_ERRORS} parameter(s) not correctly configured."
    echo "  Edit scripts/start_vllm.sh to fix."
    exit 1
fi
echo "  All tuning parameters verified."
echo ""

# ── Step 3: Restart if requested ──
if [ "${RESTART}" = true ]; then
    echo "── Step 3: Restart vLLM with Tuned Parameters ──"
    bash "${SCRIPT_DIR}/stop_vllm.sh" || true
    sleep 2
    bash "${SCRIPT_DIR}/start_vllm.sh" --daemon
    echo ""
fi

# ── Step 4: Verify server is running ──
echo "── Step 4: Verify Server ──"
if ! curl -sf "${BASE_URL}/v1/models" >/dev/null 2>&1; then
    echo "  [ERROR] vLLM server not reachable at ${BASE_URL}"
    echo "  Start with: bash scripts/start_vllm.sh --daemon"
    exit 1
fi

# Verify model is loaded
MODEL_RESP=$(curl -sf "${BASE_URL}/v1/models")
LOADED_MODEL=$(echo "${MODEL_RESP}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['id'] for m in data.get('data', [])]
print(','.join(models))
" 2>/dev/null || echo "unknown")
echo "  [OK] Server running. Loaded model(s): ${LOADED_MODEL}"
echo ""

# ── Step 5: Run benchmark ──
echo "── Step 5: Run Benchmark ──"
echo ""
bash "${SCRIPT_DIR}/benchmark_vllm.sh"
BENCH_EXIT=$?

echo ""
echo "=========================================="
if [ "${BENCH_EXIT}" -eq 0 ]; then
    echo "  ✅ TUNING VALIDATION PASSED"
    echo ""
    echo "  Parameters verified:"
    echo "    tensor-parallel-size:    2"
    echo "    enable-prefix-caching:   yes"
    echo "    gpu-memory-utilization:  0.85"
    echo "    max-model-len:           8192"
    echo "    max-num-seqs:            64"
    echo ""
    echo "  Performance:"
    echo "    TTFT < 2s:       PASS"
    echo "    Throughput > 20: PASS"
else
    echo "  ❌ TUNING VALIDATION FAILED"
    echo ""
    echo "  Review benchmark output above for details."
    echo "  Try adjusting parameters and re-running:"
    echo "    VLLM_MAX_MODEL_LEN=4096 bash scripts/start_vllm.sh --daemon"
    echo "    bash scripts/tune_vllm.sh"
fi
echo "=========================================="
exit "${BENCH_EXIT}"
