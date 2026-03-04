#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Sirus AI CRM — 开发环境状态检查脚本
# 用法: bash scripts/dev_status.sh
# 检查各服务进程状态 + 查看最新日志
# ============================================================

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

LOG_DIR="~/ai-crm/logs"
LOG_TAIL_LINES=10

# ── 服务定义 ──
declare -a HOSTS=("4090"       "mac_min_8T" "gateway")
declare -a NAMES=("agent"      "crm"        "dingtalk")
declare -a MODULES=("agent.main" "crm.main" "deploy.dingtalk.stub_server")
declare -a PORTS=("8100"       "8900"       "9000")

# ── 检查函数 ──
check_service() {
    local host="$1"
    local name="$2"
    local module="$3"
    local port="$4"

    echo -e "${BOLD}${CYAN}── ${name} (${host}:${port}) ──${NC}"

    # 检查进程
    local pids
    pids=$(ssh "$host" "pgrep -f 'uvicorn ${module}'" 2>/dev/null || true)

    if [[ -n "$pids" ]]; then
        echo -e "  状态: ${GREEN}${BOLD}运行中${NC}"
        echo -e "  PID:  ${pids//$'\n'/, }"

        # 获取进程信息
        local proc_info
        proc_info=$(ssh "$host" "ps -p $(echo $pids | tr '\n' ',' | sed 's/,$//') -o pid,user,%cpu,%mem,etime --no-headers" 2>/dev/null || true)
        if [[ -n "$proc_info" ]]; then
            echo -e "  ${CYAN}PID      USER     %CPU  %MEM  ELAPSED${NC}"
            while IFS= read -r line; do
                echo "  $line"
            done <<< "$proc_info"
        fi
    else
        echo -e "  状态: ${RED}${BOLD}未运行${NC}"
    fi

    # 查看最新日志
    local log_file="${LOG_DIR}/${name}.log"
    echo ""
    echo -e "  ${YELLOW}最近 ${LOG_TAIL_LINES} 行日志 (${log_file}):${NC}"
    local log_content
    log_content=$(ssh "$host" "tail -n ${LOG_TAIL_LINES} ${log_file} 2>/dev/null" 2>/dev/null || true)
    if [[ -n "$log_content" ]]; then
        while IFS= read -r line; do
            echo "    $line"
        done <<< "$log_content"
    else
        echo -e "    ${YELLOW}(日志文件不存在或为空)${NC}"
    fi

    echo ""
}

# ── 主流程 ──
echo ""
echo -e "${BOLD}${CYAN}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  Sirus AI CRM — 开发环境状态${NC}"
echo -e "${BOLD}${CYAN}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BOLD}${CYAN}════════════════════════════════════════════════${NC}"
echo ""

for i in "${!HOSTS[@]}"; do
    check_service "${HOSTS[$i]}" "${NAMES[$i]}" "${MODULES[$i]}" "${PORTS[$i]}"
done

# ── 汇总 ──
echo -e "${BOLD}${CYAN}── 汇总 ──${NC}"
RUNNING=0
STOPPED=0
for i in "${!HOSTS[@]}"; do
    if ssh "${HOSTS[$i]}" "pgrep -f 'uvicorn ${MODULES[$i]}' > /dev/null 2>&1"; then
        RUNNING=$((RUNNING + 1))
    else
        STOPPED=$((STOPPED + 1))
    fi
done

echo -e "  ${GREEN}运行中: ${RUNNING}${NC}  ${RED}未运行: ${STOPPED}${NC}  总计: ${#HOSTS[@]}"
echo ""

if [[ "$STOPPED" -gt 0 ]]; then
    echo -e "${YELLOW}提示: 使用 ${BOLD}bash scripts/dev_start.sh${NC}${YELLOW} 启动未运行的服务${NC}"
    echo ""
fi
