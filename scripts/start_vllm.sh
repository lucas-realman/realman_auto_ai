#!/bin/bash
# vLLM 部署脚本 - 检查 GPU、安装 vLLM、启动 Qwen3-30B-A3B 推理服务
# 运行位置: W1 (4090, 172.16.11.194)
# 验收: curl localhost:8000/v1/models 返回模型名

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="Qwen/Qwen3-30B-A3B"
VLLM_PORT=8000

echo "=== vLLM 部署开始 ==="

# 1. 检查 NVIDIA 驱动和 GPU
echo "[1/4] 检查 GPU 状态..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "错误: nvidia-smi 未找到，请先安装 NVIDIA 驱动"
    exit 1
fi

GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
echo "检测到 ${GPU_COUNT} 个 GPU:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

if [ "$GPU_COUNT" -lt 2 ]; then
    echo "警告: 检测到少于 2 个 GPU，建议使用 2×4090"
fi

# 2. 安装 vLLM
echo "[2/4] 安装 vLLM..."
pip install -q -r "${SCRIPT_DIR}/requirements-vllm.txt"

# 3. 检查模型是否存在
echo "[3/4] 检查模型..."
if [ ! -d "$HOME/.cache/huggingface/hub" ]; then
    echo "提示: 首次运行将下载模型，可能需要较长时间"
fi

# 4. 启动 vLLM 服务
echo "[4/4] 启动 vLLM 推理服务..."
echo "模型: ${MODEL_NAME}"
echo "端口: ${VLLM_PORT}"
echo "Tensor Parallel: 2 (使用 2×4090)"

python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_NAME}" \
    --port ${VLLM_PORT} \
    --tensor-parallel-size 2 \
    --gpu-memory-utilization 0.85 \
    --enable-prefix-caching \
    --max-model-len 8192 \
    --trust-remote-code

echo "=== vLLM 服务已启动 ==="
