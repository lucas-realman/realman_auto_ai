#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Sirus AI CRM — 全节点健康巡检脚本
# 用法: bash scripts/check_health.sh
# 可在任意机器执行
# ============================================================

# ── 颜色定义 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── 配置 ──
CRM_URL="http://172.16.12.50:8900/health"
AGENT_URL="http://172.16.11.194:8100/health"
DINGTALK_URL="http://172.16.14.215:9000/health"
VLLM_URL="http://172.16.11.194:8000/health"
PG_HOST="172.16.12.50"
PG_PORT="5432"
REDIS_HOST="172.16.12.50"

CURL_TIMEOUT=5

# ── 结果收集 ──
declare -a RESULTS=()
FAIL_COUNT=0

# ── 检查函数 ──
check_http() {
    local name="$1"
    local url="$2"
    local start end elapsed status

    start=$(date +%s%N)
    if status=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout "$CURL_TIMEOUT" --max-time "$CURL_TIMEOUT" "$url" 2>/dev/null); then
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))
        if [[ "$status" == "200" ]]; then
            RESULTS+=("${name}|${GREEN}✔ OK${NC}|${elapsed}ms")
        else
            RESULTS+=("${name}|${YELLOW}⚠ HTTP ${status}${NC}|${elapsed}ms")
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))
        RESULTS+=("${name}|${RED}✘ FAIL${NC}|${elapsed}ms")
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

check_postgres() {
    local name="PostgreSQL"
    local start end elapsed

    start=$(date +%s%N)
    if command -v pg_isready &>/dev/null; then
        if pg_isready -h "$PG_HOST" -p "$PG_PORT" -t "$CURL_TIMEOUT" &>/dev/null; then
            end=$(date +%s%N)
            elapsed=$(( (end - start) / 1000000 ))
            RESULTS+=("${name}|${GREEN}✔ OK${NC}|${elapsed}ms")
        else
            end=$(date +%s%N)
            elapsed=$(( (end - start) / 1000000 ))
            RESULTS+=("${name}|${RED}✘ FAIL${NC}|${elapsed}ms")
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))
        RESULTS+=("${name}|${YELLOW}⚠ pg_isready not found${NC}|${elapsed}ms")
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

check_redis() {
    local name="Redis"
    local start end elapsed

    start=$(date +%s%N)
    if command -v redis-cli &>/dev/null; then
        if redis-cli -h "$REDIS_HOST" ping 2>/dev/null | grep -q "PONG"; then
            end=$(date +%s%N)
            elapsed=$(( (end - start) / 1000000 ))
            RESULTS+=("${name}|${GREEN}✔ OK${NC}|${elapsed}ms")
        else
            end=$(date +%s%N)
            elapsed=$(( (end - start) / 1000000 ))
            RESULTS+=("${name}|${RED}✘ FAIL${NC}|${elapsed}ms")
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    else
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))
        RESULTS+=("${name}|${YELLOW}⚠ redis-cli not found${NC}|${elapsed}ms")
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# ── 打印表头 ──
print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║         Sirus AI CRM — 全节点健康巡检                   ║${NC}"
    echo -e "${BOLD}${CYAN}║         $(date '+%Y-%m-%d %H:%M:%S')                              ║${NC}"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
    printf "${BOLD}${CYAN}║${NC} %-20s ${CYAN}│${NC} %-18s ${CYAN}│${NC} %-10s ${CYAN}║${NC}\n" "服务" "状态" "响应时间"
    echo -e "${BOLD}${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
}

print_row() {
    local name status latency
    IFS='|' read -r name status latency <<< "$1"
    printf "${CYAN}║${NC} %-20s ${CYAN}│${NC} %-27b ${CYAN}│${NC} %-10s ${CYAN}║${NC}\n" "$name" "$status" "$latency"
}

print_footer() {
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    if [[ "$FAIL_COUNT" -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}✔ 所有服务正常运行！${NC}"
    else
        echo -e "${RED}${BOLD}✘ ${FAIL_COUNT} 个服务异常，请检查！${NC}"
    fi
    echo ""
}

# ── 执行检查 ──
echo -e "\n${CYAN}正在巡检各节点...${NC}\n"

check_http    "CRM 后端"       "$CRM_URL"
check_http    "Agent 引擎"     "$AGENT_URL"
check_http    "DingTalk 桩"    "$DINGTALK_URL"
check_http    "vLLM 推理"      "$VLLM_URL"
check_postgres
check_redis

# ── 输出结果 ──
print_header
for row in "${RESULTS[@]}"; do
    print_row "$row"
done
print_footer

# 返回码: 有失败则返回 1
[[ "$FAIL_COUNT" -eq 0 ]] && exit 0 || exit 1
