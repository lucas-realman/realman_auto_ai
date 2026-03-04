#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Sirus AI CRM — 开发环境停止脚本
# 用法: bash scripts/dev_stop.sh
# 通过 SSH 到各机器停止 uvicorn 服务
# ============================================================

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── 停止函数 ──
stop_service() {
    local host="$1"
    local name="$2"
    local module="$3"

    echo -e "${CYAN}[停止]${NC} ${BOLD}${name}${NC} (${host}) ..."

    if ssh "$host" "pgrep -f 'uvicorn ${module}' > /dev/null 2>&1"; then
        ssh "$host" "pkill -f 'uvicorn ${module}'" 2>/dev/null || true
        sleep 1
        # 确认已停止
        if ssh "$host" "pgrep -f 'uvicorn ${module}' > /dev/null 2>&1"; then
            echo -e "  ${YELLOW}⚠ 进程仍在运行，尝试强制终止...${NC}"
            ssh "$host" "pkill -9 -f 'uvicorn ${module}'" 2>/dev/null || true
            sleep 1
        fi

        if ssh "$host" "pgrep -f 'uvicorn ${module}' > /dev/null 2>&1"; then
            echo -e "  ${RED}✘ 无法停止，请手动处理${NC}"
        else
            echo -e "  ${GREEN}✔ 已停止${NC}"
        fi
    else
        echo -e "  ${YELLOW}⚠ 未在运行${NC}"
    fi
}

# ── 主流程 ──
echo ""
echo -e "${BOLD}${CYAN}════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  Sirus AI CRM — 开发环境停止${NC}"
echo -e "${BOLD}${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BOLD}${CYAN}════════════════════════════════════════${NC}"
echo ""

stop_service "4090"       "agent"    "agent.main"
stop_service "mac_min_8T" "crm"      "crm.main"
stop_service "gateway"    "dingtalk" "deploy.dingtalk.stub_server"

echo ""
echo -e "${GREEN}${BOLD}✔ 停止操作完成${NC}"
echo ""
