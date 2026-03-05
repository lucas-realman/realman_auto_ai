#!/usr/bin/env bash
# ============================================================
# install_vllm.sh — Install vLLM and dependencies for 2×4090
#
# Usage:
#   bash scripts/install_vllm.sh
#
# Prerequisites:
#   - Python 3.11+
#   - NVIDIA driver with CUDA 12.x support
#   - pip
#
# This script:
#   1. Creates a Python venv at .venv-vllm (if not exists)
#   2. Installs vLLM + dependencies from requirements-vllm.txt
#   3. Verifies installation
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
VENV_DIR="${PROJECT_ROOT}/.venv-vllm"
REQUIREMENTS="${SCRIPT_DIR}/requirements-vllm.txt"

echo "=========================================="
echo "  vLLM Installation"
echo "=========================================="

# --- Check Python ---
PYTHON_CMD=""
for cmd in python3.11 python3 python; do
    if command -v "${cmd}" &>/dev/null; then
        PYTHON_CMD="${cmd}"
        break
    fi
done

if [ -z "${PYTHON_CMD}" ]; then
    echo "[ERROR] Python 3 not found. Please install Python 3.11+."
    exit 1
fi

PYTHON_VERSION=$("${PYTHON_CMD}" --version 2>&1)
echo "[OK] Using ${PYTHON_VERSION} (${PYTHON_CMD})"

# --- Create virtualenv ---
if [ ! -d "${VENV_DIR}" ]; then
    echo "[INFO] Creating virtual environment at ${VENV_DIR} ..."
    "${PYTHON_CMD}" -m venv "${VENV_DIR}"
    echo "[OK] Virtual environment created."
else
    echo "[OK] Virtual environment already exists at ${VENV_DIR}"
fi

# --- Activate venv ---
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo "[OK] Activated venv: $(which python)"

# --- Upgrade pip ---
echo "[INFO] Upgrading pip ..."
pip install --upgrade pip setuptools wheel --quiet

# --- Install requirements ---
if [ -f "${REQUIREMENTS}" ]; then
    echo "[INFO] Installing from ${REQUIREMENTS} ..."
    pip install -r "${REQUIREMENTS}"
else
    echo "[WARN] ${REQUIREMENTS} not found, installing vllm directly ..."
    pip install vllm
fi

# --- Verify installation ---
echo ""
echo "--- Verifying vLLM installation ---"
python -c "import vllm; print(f'[OK] vLLM version: {vllm.__version__}')"

echo ""
echo "=========================================="
echo "  vLLM installation COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Check GPUs:     bash scripts/check_gpu.sh"
echo "  2. Download model: huggingface-cli download Qwen/Qwen3-30B-A3B"
echo "  3. Start server:   bash scripts/start_vllm.sh"
exit 0
