#!/usr/bin/env bash
# ============================================================
# Sirus AI CRM — Nginx 配置安装脚本
# 运行位置: gateway (172.16.14.215)
# 用法: bash deploy/nginx/install.sh
#
# 注意: gateway 机器使用 realman 用户，没有 sudo 权限。
#       脚本会将配置复制到用户可写目录，需手动 link 到 Nginx。
# ============================================================
set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_SRC="${SCRIPT_DIR}/ai-crm.conf"
NGINX_AVAILABLE="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"
CONF_NAME="ai-crm.conf"

echo -e "${GREEN}[1/4]${NC} 检查配置文件..."
if [ ! -f "${CONF_SRC}" ]; then
    echo -e "${RED}错误: 找不到 ${CONF_SRC}${NC}"
    exit 1
fi
echo -e "      源文件: ${CONF_SRC}"

echo -e "${GREEN}[2/4]${NC} 复制配置到 Nginx..."
if [ -w "${NGINX_AVAILABLE}" ]; then
    cp "${CONF_SRC}" "${NGINX_AVAILABLE}/${CONF_NAME}"
    echo -e "      已复制到 ${NGINX_AVAILABLE}/${CONF_NAME}"
else
    echo -e "${YELLOW}警告: 无写入权限 ${NGINX_AVAILABLE}${NC}"
    echo -e "      请手动执行:"
    echo -e "        sudo cp ${CONF_SRC} ${NGINX_AVAILABLE}/${CONF_NAME}"
    echo -e "        sudo ln -sf ${NGINX_AVAILABLE}/${CONF_NAME} ${NGINX_ENABLED}/${CONF_NAME}"
fi

echo -e "${GREEN}[3/4]${NC} 测试 Nginx 配置..."
if command -v nginx &> /dev/null; then
    if nginx -t 2>&1; then
        echo -e "      ${GREEN}配置测试通过${NC}"
    else
        echo -e "      ${RED}配置测试失败，请检查错误${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}警告: nginx 命令不可用，跳过测试${NC}"
    echo -e "      请手动执行: sudo nginx -t"
fi

echo -e "${GREEN}[4/4]${NC} 重载 Nginx..."
if command -v nginx &> /dev/null && [ -w "${NGINX_AVAILABLE}" ]; then
    nginx -s reload
    echo -e "      ${GREEN}Nginx 已重载${NC}"
else
    echo -e "${YELLOW}提示: 请手动执行:${NC}"
    echo -e "        sudo ln -sf ${NGINX_AVAILABLE}/${CONF_NAME} ${NGINX_ENABLED}/${CONF_NAME}"
    echo -e "        sudo nginx -t && sudo nginx -s reload"
fi

echo ""
echo -e "${GREEN}完成!${NC} 可通过以下地址验证:"
echo -e "  CRM 健康检查:   curl http://localhost/health/crm"
echo -e "  Agent 健康检查:  curl http://localhost/health/agent"
echo -e "  CRM API:        curl http://localhost/api/v1/leads"
echo -e "  Agent Chat:     curl -X POST http://localhost/agent/chat"
