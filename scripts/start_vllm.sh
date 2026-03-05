#!/usr/bin/env bash
# ============================================================
# start_vllm.sh — Start vLLM inference server for Qwen3-30B-A3B
#
# Usage:
#   bash scripts/start_vllm.sh              # foreground
#   bash scripts/start_vllm.sh --daemon     # background (logs to file)
#
# Configuration (override via environment variables):
#   VLLM_MODEL          Model name/path        (default: Qwen/Qwen3-30B-A3B)
#   VLLM_HOST           Bind host              (default: 0.0.0.0)
#   VLLM_PORT           Bind port              (default: 8000)
#   VLLM_TP_SIZE        Tensor parallel size   (default: 2, for 2×4090)
#   VLLM_GPU_UTIL       GPU memory utilization (default: 0.85)
#   VLLM_MAX_MODEL_LEN  Max sequence length    (default: 8192)
#   VLLM_MAX_NUM_SEQS   Max concurrent seqs    (default: 64)
#   VLLM_LOG_DIR        Log directory          (default: logs/)
#
# Acceptance:
#   curl http://localhost:8000/v1/models  → returns model name
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

# --- Configuration with defaults ---
MODEL="${VLLM_MODEL:-Qwen/Qwen3-30B-A3B}"
HOST="${VLLM_HOST:-0.0.0.0}"
PORT="${VLLM_PORT:-8000}"
TP_SIZE="${VLLM_TP_SIZE:-2}"
GPU_MEMORY_UTIL="${VLLM_GPU_UTIL:-0.85}"
MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-64}"
LOG_DIR="${VLLM_LOG_DIR:-${PROJECT_ROOT}/logs}"
PID_FILE="${PROJECT_ROOT}/.vllm.pid"
DAEMON_MODE=false

# --- Parse arguments ---
for arg in "$@"; do
    case "${arg}" in
        --daemon|-d)
            DAEMON_MODE=true
            ;;
        --help|-h)
            head -25 "$0" | tail -22
            exit 0
            ;;
    esac
done

# --- Activate venv if available ---
VENV_DIR="${PROJECT_ROOT}/.venv-vllm"
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
    echo "[OK] Activated venv: ${VENV_DIR}"
fi

# --- Pre-flight checks ---
echo "=========================================="
echo "  vLLM Pre-flight Checks"
echo "=========================================="

# Check nvidia-smi
if ! command -v nvidia-smi &>/dev/null; then
    echo "[ERROR] nvidia-smi not found. NVIDIA driver may not be installed."
    echo "        Run: bash scripts/check_gpu.sh  for detailed diagnostics."
    exit 1
fi

GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
echo "[OK] Detected ${GPU_COUNT} GPU(s)"
nvidia-smi --query-gpu=index,name,memory.total,memory.free \
    --format=csv,noheader | while IFS= read -r line; do
    echo "     ${line}"
done

if [ "${GPU_COUNT}" -lt "${TP_SIZE}" ]; then
    echo "[ERROR] Tensor parallel size (${TP_SIZE}) exceeds GPU count (${GPU_COUNT})."
    echo "        Set VLLM_TP_SIZE=${GPU_COUNT} or add more GPUs."
    exit 1
fi

# Check vLLM is installed
if ! python -c "import vllm" 2>/dev/null; then
    echo "[ERROR] vLLM not installed. Run: pip install -r scripts/requirements-vllm.txt"
    exit 1
fi

VLLM_VERSION=$(python -c "import vllm; print(vllm.__version__)")
echo "[OK] vLLM version: ${VLLM_VERSION}"

# --- Check if already running ---
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "[WARN] vLLM already running (PID ${OLD_PID})."
        echo "       Use 'bash scripts/stop_vllm.sh' to stop it first."
        exit 1
    else
        echo "[INFO] Stale PID file found, removing."
        rm -f "${PID_FILE}"
    fi
fi

# --- Create log directory ---
mkdir -p "${LOG_DIR}"

echo ""
echo "=========================================="
echo "  Starting vLLM Inference Server"
echo "=========================================="
echo "  Model:            ${MODEL}"
echo "  Host:             ${HOST}"
echo "  Port:             ${PORT}"
echo "  Tensor Parallel:  ${TP_SIZE}"
echo "  GPU Mem Util:     ${GPU_MEMORY_UTIL}"
echo "  Max Model Len:    ${MAX_MODEL_LEN}"
echo "  Max Num Seqs:     ${MAX_NUM_SEQS}"
echo "  Daemon Mode:      ${DAEMON_MODE}"
echo "=========================================="

# --- Build command ---
VLLM_CMD=(
    python -m vllm.entrypoints.openai.api_server
    --model "${MODEL}"
    --host "${HOST}"
    --port "${PORT}"
    --tensor-parallel-size "${TP_SIZE}"
    --gpu-memory-utilization "${GPU_MEMORY_UTIL}"
    --max-model-len "${MAX_MODEL_LEN}"
    --max-num-seqs "${MAX_NUM_SEQS}"
    --enable-prefix-caching
    --trust-remote-code
    --dtype auto
)

if [ "${DAEMON_MODE}" = true ]; then
    LOG_FILE="${LOG_DIR}/vllm_$(date +%Y%m%d_%H%M%S).log"
    echo "[INFO] Running in daemon mode. Logs: ${LOG_FILE}"

    nohup "${VLLM_CMD[@]}" > "${LOG_FILE}" 2>&1 &
    VLLM_PID=$!
    echo "${VLLM_PID}" > "${PID_FILE}"
    echo "[OK] vLLM started in background (PID ${VLLM_PID})"

    # --- Wait for server to be ready ---
    echo "[INFO] Waiting for vLLM to become ready ..."
    MAX_WAIT=300  # 5 minutes (model loading can take a while)
    WAITED=0
    while [ "${WAITED}" -lt "${MAX_WAIT}" ]; do
        if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
            echo ""
            echo "[ERROR] vLLM process exited unexpectedly. Check ${LOG_FILE}"
            rm -f "${PID_FILE}"
            exit 1
        fi
        if curl -sf "http://localhost:${PORT}/v1/models" >/dev/null 2>&1; then
            echo ""
            echo "[OK] vLLM is ready! (waited ${WAITED}s)"
            echo ""
            echo "Verify with:"
            echo "  curl http://localhost:${PORT}/v1/models"
            exit 0
        fi
        sleep 5
        WAITED=$((WAITED + 5))
        printf "."
    done
    echo ""
    echo "[ERROR] vLLM did not become ready within ${MAX_WAIT}s. Check ${LOG_FILE}"
    exit 1
else
    echo "[INFO] Running in foreground (Ctrl+C to stop) ..."
    exec "${VLLM_CMD[@]}"
fi
