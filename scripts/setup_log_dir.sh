#!/usr/bin/env bash
# Sirus AI CRM — 日志目录初始化脚本
#
# 功能:
#   1. 创建 /var/log/ai-crm 目录
#   2. 设置合适的权限（当前用户可写）
#   3. 验证目录可用性
#
# 用法:
#   sudo bash scripts/setup_log_dir.sh
#
# 说明:
#   - 各服务日志文件: /var/log/ai-crm/{service}.jsonl
#   - 服务名: crm, agent, gateway, celery

set -euo pipefail

LOG_DIR="${AI_CRM_LOG_DIR:-/var/log/ai-crm}"
RUN_USER="${SUDO_USER:-$(whoami)}"

echo "=== Sirus AI CRM 日志目录初始化 ==="
echo "日志目录: ${LOG_DIR}"
echo "运行用户: ${RUN_USER}"

# 1. 创建目录
if [ ! -d "${LOG_DIR}" ]; then
    echo "[1/3] 创建日志目录 ${LOG_DIR} ..."
    mkdir -p "${LOG_DIR}"
    echo "      ✅ 目录已创建"
else
    echo "[1/3] 日志目录已存在，跳过创建"
fi

# 2. 设置权限
echo "[2/3] 设置目录权限 ..."
chown -R "${RUN_USER}":"${RUN_USER}" "${LOG_DIR}" 2>/dev/null || {
    # 如果 chown 失败（非 root），尝试 chmod
    echo "      ⚠️  chown 失败（需要 sudo），尝试 chmod ..."
    chmod -R 777 "${LOG_DIR}" 2>/dev/null || true
}
chmod 755 "${LOG_DIR}"
echo "      ✅ 权限设置完成"

# 3. 验证可写
echo "[3/3] 验证目录可写 ..."
TEST_FILE="${LOG_DIR}/.write_test"
if touch "${TEST_FILE}" 2>/dev/null; then
    rm -f "${TEST_FILE}"
    echo "      ✅ 目录可写"
else
    echo "      ❌ 目录不可写！请使用 sudo 运行此脚本。"
    exit 1
fi

echo ""
echo "=== 初始化完成 ==="
echo "预期日志文件:"
echo "  ${LOG_DIR}/crm.jsonl       — CRM 后端"
echo "  ${LOG_DIR}/agent.jsonl     — Agent 引擎"
echo "  ${LOG_DIR}/gateway.jsonl   — 钉钉网关"
echo "  ${LOG_DIR}/celery.jsonl    — Celery Worker"
echo ""
echo "在各服务中使用:"
echo "  from scripts.log_config import setup_logging"
echo "  setup_logging('crm')  # 或 agent / gateway / celery"
