#!/usr/bin/env bash
# ============================================================
# Sirus AI-CRM — Orchestrator 调度脚本 v2.0
# 职责: 解析任务卡 → SSH 分发 aider → 收集结果 → 汇总通知
# 用法: bash dispatch.sh [branch] [commit_sha]
# 改进:
#   - 动态读取 contracts/ 下所有契约文件作为 aider --read
#   - 从任务卡 ### T{n} 节提取详细说明作为 aider message
#   - 支持 --dry-run 模式 (只解析不执行)
# ============================================================
set -euo pipefail

# ---- 配置 ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$HOME/ai-crm"
LOG_DIR="$HOME/ai-crm-pipeline/logs"
TASK_CARD="docs/task-card.md"
MAX_RETRIES=3
DRY_RUN=false

# 解析命令行参数
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true; shift ;;
    esac
done

# 分支和 commit（由 post-receive hook 传入）
BRANCH="${1:-main}"
COMMIT="${2:-HEAD}"

# aider 环境变量
AIDER_API_BASE="http://120.133.40.59/api"
AIDER_API_KEY="sk-JlAwhuzfB7XrZELM1qw9pGBI3vyi8jTZVgIYCUkHesc6lbhQ"
AIDER_MODEL="openai/claude-opus-4-6"

# 各机器 aider 激活前缀（处理不同安装方式）
declare -A AIDER_PREFIX
AIDER_PREFIX[4090]='export PATH="$HOME/.local/bin:$PATH"'
AIDER_PREFIX[mac_min_8T]='export PATH="$HOME/Library/Python/3.9/bin:$PATH"'
AIDER_PREFIX[gateway]='source ~/.venv/aider/bin/activate'
AIDER_PREFIX[data_center]='export PATH="$HOME/miniconda3/bin:$PATH" && source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate aider'
AIDER_PREFIX[orchestrator]='export PATH="$HOME/.local/bin:$PATH"'

# Git 远程仓库
GIT_REMOTE="edge_sale@172.16.12.50:git/ai-crm.git"

# ---- 日志函数 ----
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="$LOG_DIR/dispatch_${TIMESTAMP}.log"

log() {
    local level="$1"; shift
    echo "[$(date '+%H:%M:%S')] [$level] $*" | tee -a "$LOGFILE"
}

log_info()  { log "INFO"  "$@"; }
log_ok()    { log " OK "  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "FAIL"  "$@"; }

# ---- 构建契约 --read 参数 ----
# 收集 contracts/ 下所有 yaml/sql 文件作为 aider 只读参考
build_contract_reads() {
    local reads=""
    for f in contracts/*.yaml contracts/*.sql; do
        [[ -f "$f" ]] && reads="$reads --read $f"
    done
    # 任务卡本身也作为参考
    reads="$reads --read $TASK_CARD"
    echo "$reads"
}

# ---- 从任务卡提取某个 T{n} 的详细说明 ----
# 解析 ### T{n} 到下一个 ### T 或 --- 之间的文本
extract_task_detail() {
    local tid="$1"
    local card="$REPO_DIR/$TASK_CARD"
    local capturing=false
    local detail=""

    while IFS= read -r line; do
        # 匹配 ### T1 或 ### T2 等开头
        if [[ "$line" =~ ^###[[:space:]]+${tid}[[:space:]] ]]; then
            capturing=true
            continue
        fi
        # 遇到下一个 ### T 或 --- 停止
        if $capturing; then
            if [[ "$line" =~ ^###[[:space:]]+T[0-9] ]] || [[ "$line" == "---" ]]; then
                break
            fi
            detail+="$line"$'\n'
        fi
    done < "$card"

    echo "$detail"
}

# ---- 阶段 0: 拉取最新代码 ----
phase_pull() {
    log_info "=== 阶段 0: 拉取最新代码 (branch=$BRANCH, commit=${COMMIT:0:8}) ==="
    cd "$REPO_DIR"
    git fetch origin 2>&1 | tee -a "$LOGFILE"
    git checkout "$BRANCH" 2>&1 | tee -a "$LOGFILE"
    git reset --hard "origin/$BRANCH" 2>&1 | tee -a "$LOGFILE"
    log_ok "代码已同步到 ${COMMIT:0:8}"
}

# ---- 阶段 1: 解析任务卡 ----
# 从 task-card.md 中解析任务表格
# 格式: | T1 | mac_min_8T | ssh mac_min_8T | CRM /health API | crm/ | 5 min |
declare -A TASK_HOST TASK_DESC TASK_DIR TASK_STATUS
TASK_ORDER=()           # 有序任务 ID 列表
PARALLEL_TASKS=()       # 可并行的任务
SERIAL_TASKS=()         # 串行的任务

phase_parse() {
    log_info "=== 阶段 1: 解析任务卡 ==="
    local card="$REPO_DIR/$TASK_CARD"
    if [[ ! -f "$card" ]]; then
        log_error "任务卡不存在: $card"
        exit 1
    fi

    # 解析任务表格行 (| T1 | machine | ... | desc | dir | time |)
    while IFS='|' read -r _ tid machine _ desc dir _; do
        tid=$(echo "$tid" | xargs)
        machine=$(echo "$machine" | xargs | sed 's/ (.*//')  # 去掉 IP
        desc=$(echo "$desc" | xargs | tr -d '`')
        dir=$(echo "$dir" | xargs | tr -d '`')

        # 跳过表头和分隔线
        [[ "$tid" =~ ^T[0-9]+ ]] || continue

        TASK_ORDER+=("$tid")
        TASK_HOST["$tid"]="$machine"
        TASK_DESC["$tid"]="$desc"
        TASK_DIR["$tid"]="$dir"
        TASK_STATUS["$tid"]="pending"
        log_info "  解析到: $tid → $machine ($dir) — $desc"
    done < <(grep '^\s*|.*T[0-9]' "$card")

    # 解析执行顺序（从 "## 执行顺序" 节提取并行/串行）
    local in_order=false
    while IFS= read -r line; do
        if [[ "$line" == *"执行顺序"* ]]; then
            in_order=true; continue
        fi
        [[ "$in_order" == true ]] || continue
        [[ "$line" == "##"* && "$line" != *"执行顺序"* ]] && break

        if [[ "$line" == *"并行"* ]]; then
            # 提取所有 T[n] 标识（并行行里都是真正的并行任务）
            for t in $(echo "$line" | grep -oE 'T[0-9]+'); do
                PARALLEL_TASKS+=("$t")
            done
        elif [[ "$line" == *"串行"* ]]; then
            # 只取第一个 T[n]（后面的是依赖描述，不是任务）
            local first_t
            first_t=$(echo "$line" | grep -oE 'T[0-9]+' | head -1)
            [[ -n "$first_t" ]] && SERIAL_TASKS+=("$first_t")
        fi
    done < "$card"

    log_info "  并行任务: ${PARALLEL_TASKS[*]:-无}"
    log_info "  串行任务: ${SERIAL_TASKS[*]:-无}"
    log_ok "解析完成: ${#TASK_ORDER[@]} 个任务"
}

# ---- 阶段 2: SSH 分发 aider 编码 ----

# 在远程机器上运行 aider 编码任务
# 用法: run_aider_task <task_id>
run_aider_task() {
    local tid="$1"
    local host="${TASK_HOST[$tid]}"
    local desc="${TASK_DESC[$tid]}"
    local dir="${TASK_DIR[$tid]}"
    local prefix="${AIDER_PREFIX[$host]}"
    local task_log="$LOG_DIR/${tid}_${host}_${TIMESTAMP}.log"
    local attempt=0
    local exit_code=1

    # 构建 --read 参数（所有契约文件）
    local contract_reads
    contract_reads=$(build_contract_reads)

    # 从任务卡提取详细说明
    local task_detail
    task_detail=$(extract_task_detail "$tid")

    while (( attempt < MAX_RETRIES && exit_code != 0 )); do
        attempt=$((attempt + 1))
        log_info "[$tid] 第 ${attempt}/${MAX_RETRIES} 次执行 → $host ($dir)"

        # 构造 aider 指令 — 使用任务卡中的详细说明
        local aider_msg="你是 Sirus AI CRM 项目的开发者。请根据以下任务说明和仓库中 contracts/ 目录的接口契约，在 \`$dir\` 目录下实现代码。

## 任务: $desc

$task_detail

## 约束
1. 严格遵循 contracts/ 下的接口契约（crm-api.yaml, agent-api.yaml, agent-tools.yaml, db-schema.sql, event-bus.yaml）
2. 包含必要的 requirements.txt
3. 代码可直接运行（python -m uvicorn 或 bash 执行）
4. 只生成 \`$dir\` 目录下的文件，不要修改其他目录"

        # 如果是重试，附加修复指令
        if (( attempt > 1 )); then
            local prev_log=$(tail -30 "$task_log" 2>/dev/null || echo "无日志")
            aider_msg="上一次执行失败了，错误日志如下:
${prev_log}

请修复问题并重新实现。原始任务:
$aider_msg"
        fi

        # DRY RUN 模式：只输出不执行
        if $DRY_RUN; then
            log_info "[$tid] [DRY-RUN] → $host | dir=$dir"
            log_info "[$tid] [DRY-RUN] contracts: $contract_reads"
            log_info "[$tid] [DRY-RUN] message 长度: ${#aider_msg} chars"
            TASK_STATUS["$tid"]="passed"
            log_ok "[$tid] DRY-RUN 完成 ✅"
            return 0
        fi

        # 将 aider_msg 写入临时文件，通过 scp 传输（避免 SSH 引号转义问题）
        local msg_file="$LOG_DIR/.aider_msg_${tid}_$$"
        echo "$aider_msg" > "$msg_file"
        scp -q "$msg_file" "$host:/tmp/aider_msg_${tid}" 2>/dev/null || true

        # SSH 执行 aider
        ssh -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ExitOnForwardFailure=no "$host" "
            $prefix
            export OPENAI_API_BASE='$AIDER_API_BASE'
            export OPENAI_API_KEY='$AIDER_API_KEY'
            cd ~/ai-crm

            # 确保工作区干净
            git rebase --abort 2>/dev/null || true
            git merge --abort 2>/dev/null || true
            git checkout -- . 2>/dev/null || true
            git clean -fd 2>/dev/null || true
            git fetch origin $BRANCH
            git reset --hard origin/$BRANCH

            mkdir -p $dir

            # 读取 aider 消息
            AIDER_MSG=\$(cat /tmp/aider_msg_${tid} 2>/dev/null || echo '在 $dir 目录下实现 $desc')

            aider --model '$AIDER_MODEL' \
                  --yes-always \
                  --no-auto-commits \
                  $contract_reads \
                  --message \"\$AIDER_MSG\"
            AIDER_EXIT=\$?

            # aider 返回码矫正
            FILE_COUNT=\$(find $dir -type f -not -name '.gitkeep' 2>/dev/null | wc -l)
            if [[ \$AIDER_EXIT -ne 0 ]] && [[ \$FILE_COUNT -gt 0 ]]; then
                echo \"[WARN] aider exit=\$AIDER_EXIT but found \$FILE_COUNT files in $dir, treating as success\"
                AIDER_EXIT=0
            fi
            if [[ \$AIDER_EXIT -eq 0 ]] && [[ \$FILE_COUNT -eq 0 ]]; then
                echo \"[FAIL] aider exit=0 but no files created in $dir, treating as failure\"
                AIDER_EXIT=1
            fi

            if [[ \$AIDER_EXIT -eq 0 ]]; then
                cd ~/ai-crm
                git add -A $dir
                git checkout -- . 2>/dev/null || true
                git commit -m '[${tid}] auto by aider attempt ${attempt}: $desc' || true

                PUSHED=0
                for RETRY in 1 2 3; do
                    if git pull --rebase origin $BRANCH 2>&1; then
                        git push origin $BRANCH 2>&1 && PUSHED=1 && break
                    fi
                    git rebase --abort 2>/dev/null || true
                    if git pull --no-rebase origin $BRANCH 2>&1; then
                        git push origin $BRANCH 2>&1 && PUSHED=1 && break
                    fi
                    git merge --abort 2>/dev/null || true
                    sleep 2
                done
                if [[ \$PUSHED -ne 1 ]]; then
                    echo \"[PUSH FAILED after 3 retries]\" >&2
                    exit 1
                fi
            fi

            # 清理临时文件
            rm -f /tmp/aider_msg_${tid}
            exit \$AIDER_EXIT
        " > "$task_log" 2>&1
        exit_code=$?

        # 清理本地临时文件
        rm -f "$msg_file"

        if [[ $exit_code -eq 0 ]]; then
            TASK_STATUS["$tid"]="passed"
            log_ok "[$tid] 成功 ✅ (attempt $attempt)"
        else
            log_warn "[$tid] 失败 (attempt $attempt, exit=$exit_code)"
        fi
    done

    if [[ $exit_code -ne 0 ]]; then
        TASK_STATUS["$tid"]="failed"
        log_error "[$tid] 已达最大重试次数，标记失败 ❌"
    fi

    return $exit_code
}

# 并行执行一组任务
# 注意: bash 子进程无法更新父进程的关联数组，用临时文件传递状态
run_parallel() {
    local tasks=("$@")
    local pids=()
    local results=()
    local status_dir="$LOG_DIR/.parallel_status_$$"
    mkdir -p "$status_dir"

    log_info "=== 并行执行: ${tasks[*]} ==="
    for tid in "${tasks[@]}"; do
        (
            run_aider_task "$tid"
            echo "${TASK_STATUS[$tid]}" > "$status_dir/$tid"
        ) &
        pids+=($!)
        log_info "  启动 $tid (PID ${pids[-1]})"
    done

    # 等待全部完成
    local all_ok=true
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then
            results+=("${tasks[$i]}:ok")
        else
            results+=("${tasks[$i]}:fail")
            all_ok=false
        fi
    done

    # 从临时文件读取子进程的状态更新
    for tid in "${tasks[@]}"; do
        if [[ -f "$status_dir/$tid" ]]; then
            TASK_STATUS["$tid"]=$(cat "$status_dir/$tid")
        fi
    done
    rm -rf "$status_dir"

    log_info "并行结果: ${results[*]}"
    $all_ok
}

# 串行执行一组任务
run_serial() {
    local tasks=("$@")
    log_info "=== 串行执行: ${tasks[*]} ==="
    for tid in "${tasks[@]}"; do
        if ! run_aider_task "$tid"; then
            log_error "串行任务 $tid 失败，后续任务跳过"
            return 1
        fi
    done
}

phase_dispatch() {
    log_info "=== 阶段 2: SSH 分发 aider 编码 ==="

    # Step 1: 并行任务
    if [[ ${#PARALLEL_TASKS[@]} -gt 0 ]]; then
        if ! run_parallel "${PARALLEL_TASKS[@]}"; then
            log_warn "部分并行任务失败，继续串行阶段（降级模式）"
        fi
    fi

    # Step 2: 串行任务（不用 || true，让失败状态保留在 TASK_STATUS 中）
    if [[ ${#SERIAL_TASKS[@]} -gt 0 ]]; then
        run_serial "${SERIAL_TASKS[@]}" || log_warn "部分串行任务失败"
    fi
}

# ---- 阶段 3: 结果汇总 ----
phase_report() {
    log_info "=== 阶段 3: 结果汇总 ==="

    local total=${#TASK_ORDER[@]}
    local passed=0
    local failed=0

    echo "" >> "$LOGFILE"
    echo "╔══════════════════════════════════════════╗" | tee -a "$LOGFILE"
    echo "║       Sirus AI-CRM 调度报告              ║" | tee -a "$LOGFILE"
    echo "╠══════════════════════════════════════════╣" | tee -a "$LOGFILE"
    printf "║  分支: %-33s ║\n" "$BRANCH" | tee -a "$LOGFILE"
    printf "║  提交: %-33s ║\n" "${COMMIT:0:8}" | tee -a "$LOGFILE"
    printf "║  时间: %-33s ║\n" "$(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOGFILE"
    echo "╠══════════════════════════════════════════╣" | tee -a "$LOGFILE"

    for tid in "${TASK_ORDER[@]}"; do
        local status="${TASK_STATUS[$tid]}"
        local icon="❓"
        case "$status" in
            passed) icon="✅"; passed=$((passed + 1)) ;;
            failed) icon="❌"; failed=$((failed + 1)) ;;
            pending) icon="⏸️" ;;
        esac
        printf "║  %s  %-5s → %-12s  %s  ║\n" "$icon" "$tid" "${TASK_HOST[$tid]}" "${TASK_DESC[$tid]:0:15}" | tee -a "$LOGFILE"
    done

    echo "╠══════════════════════════════════════════╣" | tee -a "$LOGFILE"
    printf "║  合计: %d 通过 / %d 失败 / %d 总计       ║\n" "$passed" "$failed" "$total" | tee -a "$LOGFILE"
    echo "╚══════════════════════════════════════════╝" | tee -a "$LOGFILE"

    # 结果判定
    if (( failed == 0 )); then
        log_ok "🎉 全部任务通过！"
        return 0
    elif (( failed <= total / 2 )); then
        log_warn "⚠️ 部分任务失败，请检查日志: $LOG_DIR"
        return 1
    else
        log_error "🚨 大面积失败，需要人工介入"
        return 2
    fi
}

# ---- 阶段 4: 钉钉通知 (预留) ----
phase_notify() {
    log_info "=== 阶段 4: 通知 (S1 暂用日志输出) ==="
    log_info "完整日志: $LOGFILE"
    # TODO S3: 接入钉钉机器人 webhook
    # curl -s -X POST "$DINGTALK_WEBHOOK" -H 'Content-Type: application/json' \
    #   -d "{\"msgtype\":\"markdown\",\"markdown\":{\"title\":\"调度报告\",\"text\":\"$(cat $LOGFILE)\"}}"
}

# ---- 主流程 ----
main() {
    log_info "======================================"
    log_info "  Sirus AI-CRM Orchestrator v2.0"
    log_info "  $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "  Branch: $BRANCH  Commit: ${COMMIT:0:8}"
    [[ "$DRY_RUN" == true ]] && log_info "  *** DRY-RUN 模式 ***"
    log_info "======================================"

    # ---- 防连锁触发 ----
    # 如果最新 commit 是 aider 自动提交的，跳过本次调度
    local LOCKFILE="/tmp/ai-crm-dispatch.lock"
    # 使用 flock 原子锁防止 TOCTOU 竞态
    # 注意: 用 <> 模式打开，不截断文件（保留 TTL 时间戳）
    exec 9<>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "另一个调度正在运行 (flock)，跳过本次调度"
        exit 0
    fi
    # 检查 TTL: 如果锁文件内记录的时间 < 10 分钟，跳过（防止 hook 连锁）
    local lock_ts
    lock_ts=$(cat "$LOCKFILE" 2>/dev/null || echo 0)
    local now_ts
    now_ts=$(date +%s)
    if [[ "$lock_ts" =~ ^[0-9]+$ ]] && (( now_ts - lock_ts < 600 )); then
        log_warn "调度锁 TTL 未过期 ($((now_ts - lock_ts)) 秒前)，跳过本次调度"
        exit 0
    fi
    echo "$now_ts" > "$LOCKFILE"
    # 不 trap 删除锁文件 — 依赖 TTL 过期，防止连锁触发

    phase_pull
    phase_parse
    phase_dispatch
    phase_report
    local result=$?
    phase_notify

    log_info "调度完成 (exit=$result)"
    return $result
}

main "$@"
