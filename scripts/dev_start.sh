#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Sirus AI CRM — 开发环境启动脚本
# 用法: bash scripts/dev_start.sh
# 通过 SSH 到各机器后台启动 uvicorn 服务
# ============================================================

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

LOG_DIR="~/ai-crm/logs"

# ── 启动函数 ──
start_service() {
    local host="$1"
    local name="$2"
    local module="$3"
    local port="$4"

    echo -e "${CYAN}[启动]${NC} ${BOLD}${name}${NC} (${host}:${port}) ..."

    # 确保日志目录存在
    ssh "$host" "mkdir -p ${LOG_DIR}" 2>/dev/null || true

    # 先检查是否已在运行
    if ssh "$host" "pgrep -f 'uvicorn ${module}' > /dev/null 2>&1"; then
        echo -e "  ${YELLOW}⚠ 已在运行，跳过。如需重启请先执行 dev_stop.sh${NC}"
        return 0
    fi

    # 后台启动 uvicorn
    ssh "$host" "cd ~/ai-crm && nohup uvicorn ${module}:app --host 0.0.0.0 --port ${port} > ${LOG_DIR}/${name}.log 2>&1 &"

    # 等待片刻确认启动
    sleep 2
    if ssh "$host" "pgrep -f 'uvicorn ${module}' > /dev/null 2>&1"; then
        echo -e "  ${GREEN}✔ 启动成功${NC} (PID: $(ssh "$host" "pgrep -f 'uvicorn ${module}'" | head -1))"
    else
        echo -e "  ${RED}✘ 启动失败，请检查日志: ${LOG_DIR}/${name}.log${NC}"
        return 1
    fi
}

# ── 主流程 ──
echo ""
echo -e "${BOLD}${CYAN}════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  Sirus AI CRM — 开发环境启动${NC}"
echo -e "${BOLD}${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BOLD}${CYAN}════════════════════════════════════════${NC}"
echo ""

FAIL=0

start_service "4090"       "agent"    "agent.main"                    8100 || FAIL=$((FAIL + 1))
start_service "mac_min_8T" "crm"      "crm.main"                     8900 || FAIL=$((FAIL + 1))
start_service "gateway"    "dingtalk" "deploy.dingtalk.stub_server"   9000 || FAIL=$((FAIL + 1))

echo ""
if [[ "$FAIL" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}✔ 所有服务已启动！${NC}"
    echo -e "${CYAN}提示: 使用 ${BOLD}bash scripts/check_health.sh${NC}${CYAN} 验证服务状态${NC}"
else
    echo -e "${RED}${BOLD}✘ ${FAIL} 个服务启动失败，请检查日志${NC}"
fi
echo ""
