#!/usr/bin/env bash
# ============================================================
# check_gpu.sh — Verify NVIDIA driver and 2×RTX 4090 GPUs
#
# Usage:
#   bash scripts/check_gpu.sh
#
# Exit codes:
#   0 — All checks passed (2 GPUs detected, driver OK)
#   1 — nvidia-smi not found or driver issue
#   2 — Fewer than 2 GPUs detected
# ============================================================
set -euo pipefail

REQUIRED_GPUS=2

echo "=========================================="
echo "  GPU Health Check"
echo "=========================================="

# --- Check nvidia-smi is available ---
if ! command -v nvidia-smi &>/dev/null; then
    echo "[ERROR] nvidia-smi not found. NVIDIA driver may not be installed."
    exit 1
fi

echo "[OK] nvidia-smi found: $(command -v nvidia-smi)"

# --- Check driver version ---
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "[OK] NVIDIA Driver Version: ${DRIVER_VERSION}"

# --- Check CUDA version ---
CUDA_RUNTIME=$(nvidia-smi | grep -oP 'CUDA Version: \K[0-9.]+' || echo "unknown")
echo "[OK] CUDA Version: ${CUDA_RUNTIME}"

# --- Count GPUs ---
GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
echo "[INFO] Detected ${GPU_COUNT} GPU(s):"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader | while IFS= read -r line; do
    echo "       GPU ${line}"
done

if [ "${GPU_COUNT}" -lt "${REQUIRED_GPUS}" ]; then
    echo "[ERROR] Expected at least ${REQUIRED_GPUS} GPUs, found ${GPU_COUNT}."
    exit 2
fi

echo "[OK] ${GPU_COUNT} GPUs detected (required: ${REQUIRED_GPUS})."

# --- GPU utilization snapshot ---
echo ""
echo "--- GPU Utilization Snapshot ---"
nvidia-smi --query-gpu=index,utilization.gpu,utilization.memory,temperature.gpu --format=csv,noheader

echo ""
echo "=========================================="
echo "  All GPU checks PASSED"
echo "=========================================="
exit 0
