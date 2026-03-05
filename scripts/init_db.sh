#!/usr/bin/env bash
# ============================================================
# Sirus AI CRM — 数据库初始化脚本
# 运行位置: mac_min_8T (172.16.12.50)
# 功能: 使用 Homebrew 安装 PostgreSQL 16 + pgvector + Redis 7，
#        创建 ai_crm 数据库并启用必要扩展
# 契约依据: contracts/db-schema.sql
# 验收标准: psql -c "SELECT 1" 成功 + redis-cli ping 成功
# ============================================================

set -euo pipefail

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 检查 Homebrew ──
check_homebrew() {
    if ! command -v brew &> /dev/null; then
        log_error "Homebrew 未安装，请先安装: https://brew.sh"
        exit 1
    fi
    log_info "检测到 Homebrew: $(brew --version | head -n1)"
}

# ── 安装 PostgreSQL 16 ──
install_postgresql() {
    log_info "检查 PostgreSQL 16..."
    if brew list postgresql@16 &> /dev/null; then
        log_warn "PostgreSQL 16 已安装，跳过"
    else
        log_info "安装 PostgreSQL 16..."
        brew install postgresql@16
    fi

    # 确保 postgresql@16 的 bin 在 PATH 中
    local pg_prefix
    pg_prefix="$(brew --prefix postgresql@16)"
    if [[ -d "$pg_prefix/bin" ]] && [[ ":$PATH:" != *":$pg_prefix/bin:"* ]]; then
        export PATH="$pg_prefix/bin:$PATH"
        log_info "已将 $pg_prefix/bin 添加到 PATH"
    fi
}

# ── 启动 PostgreSQL 服务 ──
start_postgresql() {
    log_info "启动 PostgreSQL 服务..."
    brew services start postgresql@16 2>/dev/null || log_warn "PostgreSQL 服务可能已在运行"

    # 等待 PostgreSQL 启动就绪
    local retries=10
    local wait_sec=1
    while (( retries > 0 )); do
        if psql -U "$USER" -d postgres -c "SELECT 1" &> /dev/null; then
            log_info "PostgreSQL 已就绪"
            return 0
        fi
        log_info "等待 PostgreSQL 启动... (剩余重试 $retries 次)"
        sleep "$wait_sec"
        (( retries-- ))
    done

    log_error "PostgreSQL 启动超时，请手动检查: brew services list"
    exit 1
}

# ── 安装 pgvector 扩展 ──
install_pgvector() {
    log_info "检查 pgvector 扩展..."
    if brew list pgvector &> /dev/null; then
        log_warn "pgvector 已安装，跳过"
    else
        log_info "安装 pgvector..."
        brew install pgvector
    fi
}

# ── 创建 ai_crm 数据库 ──
create_database() {
    log_info "检查 ai_crm 数据库..."
    if psql -U "$USER" -d postgres -lqt | cut -d \| -f 1 | grep -qw ai_crm; then
        log_warn "数据库 ai_crm 已存在，跳过创建"
    else
        log_info "创建数据库 ai_crm..."
        psql -U "$USER" -d postgres -c "CREATE DATABASE ai_crm;" || {
            log_error "创建数据库 ai_crm 失败"
            exit 1
        }
        log_info "数据库 ai_crm 创建成功"
    fi
}

# ── 启用扩展 ──
enable_extensions() {
    log_info "在 ai_crm 中启用扩展..."
    psql -U "$USER" -d ai_crm -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' || {
        log_error "启用 uuid-ossp 扩展失败"
        exit 1
    }
    psql -U "$USER" -d ai_crm -c 'CREATE EXTENSION IF NOT EXISTS vector;' || {
        log_error "启用 vector 扩展失败"
        exit 1
    }
    log_info "扩展已启用: uuid-ossp, vector"
}

# ── 验证扩展 ──
verify_extensions() {
    log_info "验证扩展安装..."
    local ext_list
    ext_list=$(psql -U "$USER" -d ai_crm -tAc "SELECT extname FROM pg_extension;")
    local ok=true
    for ext in "uuid-ossp" "vector"; do
        if echo "$ext_list" | grep -qw "$ext"; then
            log_info "  ✓ $ext"
        else
            log_error "  ✗ $ext 未找到"
            ok=false
        fi
    done
    if [[ "$ok" != "true" ]]; then
        log_error "扩展验证失败"
        exit 1
    fi
}

# ── 安装 Redis 7 ──
install_redis() {
    log_info "检查 Redis..."
    if brew list redis &> /dev/null; then
        local redis_major
        redis_major=$(redis-server --version 2>/dev/null | grep -oE 'v=[0-9]+' | cut -d= -f2 || echo "0")
        if [[ "$redis_major" -ge 7 ]]; then
            log_warn "Redis ${redis_major}.x 已安装，跳过"
        else
            log_warn "Redis 版本 (${redis_major}) < 7，升级中..."
            brew upgrade redis
        fi
    else
        log_info "安装 Redis..."
        brew install redis
    fi
}

# ── 启动 Redis 服务 ──
start_redis() {
    log_info "启动 Redis 服务..."
    brew services start redis 2>/dev/null || log_warn "Redis 服务可能已在运行"

    # 等待 Redis 启动就绪
    local retries=10
    local wait_sec=1
    while (( retries > 0 )); do
        local reply
        reply=$(redis-cli ping 2>/dev/null || echo "")
        if [[ "$reply" == "PONG" ]]; then
            log_info "Redis 已就绪"
            return 0
        fi
        log_info "等待 Redis 启动... (剩余重试 $retries 次)"
        sleep "$wait_sec"
        (( retries-- ))
    done

    log_error "Redis 启动超时，请手动检查: brew services list"
    exit 1
}

# ── 最终验证 ──
final_verify() {
    log_info "执行最终验证..."
    local all_ok=true

    if psql -U "$USER" -d ai_crm -c "SELECT 1" > /dev/null 2>&1; then
        log_info "  ✓ psql -c 'SELECT 1' 成功"
    else
        log_error "  ✗ psql -c 'SELECT 1' 失败"
        all_ok=false
    fi

    local redis_reply
    redis_reply=$(redis-cli ping 2>/dev/null || echo "")
    if [[ "$redis_reply" == "PONG" ]]; then
        log_info "  ✓ redis-cli ping 成功"
    else
        log_error "  ✗ redis-cli ping 失败"
        all_ok=false
    fi

    if [[ "$all_ok" != "true" ]]; then
        log_error "最终验证未全部通过"
        exit 1
    fi
}

# ── 打印连接信息 ──
print_summary() {
    echo ""
    log_info "=========================================="
    log_info " 数据库初始化完成"
    log_info "=========================================="
    echo ""
    echo "PostgreSQL 连接信息:"
    echo "  数据库: ai_crm"
    echo "  用户:   $USER"
    echo "  主机:   localhost"
    echo "  端口:   5432"
    echo "  命令:   psql -U $USER -d ai_crm"
    echo ""
    echo "Redis 连接信息:"
    echo "  主机:   localhost"
    echo "  端口:   6379"
    echo "  命令:   redis-cli"
    echo ""
    log_info "下一步: 执行 Schema 迁移"
    echo "  psql -U $USER -d ai_crm -f contracts/db-schema.sql"
    echo ""
}

# ── 主流程 ──
main() {
    log_info "开始初始化 Sirus AI CRM 数据库环境..."
    echo ""

    check_homebrew
    install_postgresql
    start_postgresql
    install_pgvector
    create_database
    enable_extensions
    verify_extensions
    install_redis
    start_redis
    final_verify
    print_summary
}

main "$@"
