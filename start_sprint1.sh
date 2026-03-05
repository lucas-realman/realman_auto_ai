#!/bin/bash
# Sprint 1 启动脚本
set -e
cd "$(dirname "$0")"

mkdir -p logs

# ── PID 锁：防止重复启动 ──
PIDFILE="logs/orchestrator.pid"
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date)] 错误: orchestrator 已在运行 (PID=$OLD_PID)，先 kill 再重启"
        exit 1
    else
        echo "[$(date)] 移除过期 PID 文件 (PID=$OLD_PID 已退出)"
        rm -f "$PIDFILE"
    fi
fi

export OPENAI_API_BASE='http://120.133.40.59/api'
export OPENAI_API_KEY='sk-JlAwhuzfB7XrZELM1qw9pGBI3vyi8jTZVgIYCUkHesc6lbhQ'
export DINGTALK_WEBHOOK_URL='https://oapi.dingtalk.com/robot/send?access_token=92b137d382bc3cf8dbfd3462eaa981458f1c562980ab9c9693add40b52b7595d'
export DINGTALK_WEBHOOK_SECRET='SECcbbe3330af578ce9bae6de5c21897366822aa8df86d886bc80e441297f15be60'
export DINGTALK_APP_KEY='dingdebpmryxshlgpdc6'
export DINGTALK_APP_SECRET='yE2Os-wytZCGU9Ul4L8FTNIDl9tGElaSEF0E_MrvJvtM0FDkO5ZC7hmOmqXgpoJO'

echo "[$(date)] Sprint 1 启动..."
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT INT TERM

python3 -m orchestrator.main -v 2>&1 | tee logs/sprint1.log
