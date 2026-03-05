"""
Sirus AI-CRM 自动化流水线 — SSH 分发器
通过 SSH 在远程机器上执行 aider 编码任务。

替代 dispatch.sh 中的 run_aider_task() bash 函数，
提供 Python 原生控制、超时管理和结果收集。
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .task_models import CodingTask, MachineInfo, TaskResult

log = logging.getLogger("orchestrator.dispatcher")


class Dispatcher:
    """
    SSH 分发器: 将 CodingTask 发送到目标机器并执行 aider。
    使用 asyncio.create_subprocess_exec 调用 ssh 命令。
    """

    def __init__(self, config: Config):
        self.config = config
        self.machines = config.get_machines()

    async def dispatch_task(self, task: CodingTask) -> TaskResult:
        """
        在目标机器上执行 aider 编码任务。

        流程:
        1. scp 任务指令文件到远程 /tmp/
        2. SSH 执行: git pull → aider → 结果收集
        3. 如果成功: git add + commit + push
        """
        machine = self.machines.get(task.target_machine)
        if not machine:
            return TaskResult(
                task_id=task.task_id,
                exit_code=1,
                stderr=f"未知机器: {task.target_machine}",
            )

        start_time = time.time()
        log.info("[%s] 分发到 %s (%s@%s), 目录: %s",
                 task.task_id, machine.name, machine.user, machine.host,
                 task.target_dir)

        try:
            # 1. 构建 aider 指令
            instruction = self._build_instruction(task)

            # 2. scp 指令文件到远程
            msg_remote_path = f"/tmp/aider_msg_{task.task_id}"
            await self._scp_content(machine, instruction, msg_remote_path)

            # 3. 构建 SSH 命令
            ssh_script = self._build_ssh_script(task, machine, msg_remote_path)

            # 4. SSH 执行
            result = await self._ssh_exec(
                machine, ssh_script,
                timeout=self.config.single_task_timeout,
            )

            duration = time.time() - start_time
            result.task_id = task.task_id
            result.duration_sec = duration

            # 5. 解析变更文件
            if result.success:
                result.files_changed = self._parse_changed_files(result.stdout, task.target_dir)
                log.info("[%s] ✅ 编码成功 (%.1fs), 变更: %s",
                         task.task_id, duration, result.files_changed)
            else:
                log.warning("[%s] ❌ 编码失败 (%.1fs, exit=%d)",
                            task.task_id, duration, result.exit_code)

            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            log.error("[%s] ⏱ 超时 (%.1fs)", task.task_id, duration)
            return TaskResult(
                task_id=task.task_id,
                exit_code=124,
                stderr=f"任务超时 ({self.config.single_task_timeout}s)",
                duration_sec=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            log.error("[%s] 异常: %s", task.task_id, e, exc_info=True)
            return TaskResult(
                task_id=task.task_id,
                exit_code=1,
                stderr=str(e),
                duration_sec=duration,
            )

    async def dispatch_batch(self, tasks: List[CodingTask]) -> List[TaskResult]:
        """并行分发一批任务"""
        coros = [self.dispatch_task(task) for task in tasks]
        return await asyncio.gather(*coros)

    # ── 构建指令 ──

    def _build_instruction(self, task: CodingTask) -> str:
        """将 CodingTask 转换为 aider 可理解的自然语言指令"""
        parts = [
            f"# 编码任务 {task.task_id}\n",
            f"## 目标\n{task.description}\n",
        ]

        if task.acceptance:
            parts.append("## 验收标准\n")
            for a in task.acceptance:
                parts.append(f"- {a}\n")

        parts.append(f"""
## 约束
1. 严格遵循 contracts/ 下的接口契约 (crm-api.yaml, agent-api.yaml, agent-tools.yaml, db-schema.sql, event-bus.yaml)
2. 包含必要的 requirements.txt
3. 代码可直接运行 (python -m uvicorn 或 bash 执行)
4. 只生成 `{task.target_dir}` 目录下的文件，不要修改其他目录
5. 包含完整的错误处理和 docstring
6. 在 tests/ 目录下生成对应的 pytest 测试文件
""")

        # 如果是重试, 附加修复指令
        if task.fix_instruction:
            parts.append(f"""
## ⚠️ 修复指令 (第 {task.total_retries} 次重试)
上一轮执行存在以下问题, 请优先修复:

{task.fix_instruction}
""")

        return "\n".join(parts)

    def _build_ssh_script(
        self, task: CodingTask, machine: MachineInfo, msg_remote_path: str,
    ) -> str:
        """构建要在远程机器上执行的完整 shell 脚本"""
        branch = self.config.git_branch
        model = self.config.aider_model
        api_base = self.config.openai_api_base
        api_key = self.config.openai_api_key

        # 构建 --read 参数 (所有契约文件)
        contract_reads = ""
        contracts_dir = self.config.repo_root / "contracts"
        if contracts_dir.exists():
            for f in contracts_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".sql"):
                    contract_reads += f" --read contracts/{f.name}"

        # 任务卡也作为 --read
        contract_reads += f" --read {self.config.task_card_path}"

        return f"""
{machine.aider_prefix}
export OPENAI_API_BASE='{api_base}'
export OPENAI_API_KEY='{api_key}'
cd {machine.work_dir}

# 确保工作区干净
git rebase --abort 2>/dev/null || true
git merge --abort 2>/dev/null || true
git checkout -- . 2>/dev/null || true
git clean -fd 2>/dev/null || true
git fetch origin {branch}
git reset --hard origin/{branch}

mkdir -p {task.target_dir}

# 读取 aider 消息
AIDER_MSG=$(cat {msg_remote_path} 2>/dev/null || echo '在 {task.target_dir} 目录下实现 {task.description[:80]}')

aider --model '{model}' \\
      --yes-always \\
      --no-auto-commits \\
      {contract_reads} \\
      --message "$AIDER_MSG"
AIDER_EXIT=$?

# aider 返回码矫正
FILE_COUNT=$(find {task.target_dir} -type f -not -name '.gitkeep' 2>/dev/null | wc -l)
if [[ $AIDER_EXIT -ne 0 ]] && [[ $FILE_COUNT -gt 0 ]]; then
    echo "[WARN] aider exit=$AIDER_EXIT but found $FILE_COUNT files, treating as success"
    AIDER_EXIT=0
fi
if [[ $AIDER_EXIT -eq 0 ]] && [[ $FILE_COUNT -eq 0 ]]; then
    echo "[FAIL] aider exit=0 but no files created, treating as failure"
    AIDER_EXIT=1
fi

if [[ $AIDER_EXIT -eq 0 ]]; then
    cd {machine.work_dir}
    git add -A {task.target_dir}
    # 也 add tests/ 目录 (aider 可能生成测试文件)
    git add -A tests/ 2>/dev/null || true
    git checkout -- . 2>/dev/null || true
    git commit -m '[{task.task_id}] auto: {task.description[:60]}' || true

    PUSHED=0
    for RETRY in 1 2 3; do
        if git pull --rebase origin {branch} 2>&1; then
            git push origin {branch} 2>&1 && PUSHED=1 && break
        fi
        git rebase --abort 2>/dev/null || true
        if git pull --no-rebase origin {branch} 2>&1; then
            git push origin {branch} 2>&1 && PUSHED=1 && break
        fi
        git merge --abort 2>/dev/null || true
        sleep 2
    done
    if [[ $PUSHED -ne 1 ]]; then
        echo "[PUSH FAILED after 3 retries]" >&2
        exit 1
    fi
fi

# 清理
rm -f {msg_remote_path}
exit $AIDER_EXIT
"""

    # ── SSH 执行工具 ──

    async def _scp_content(
        self, machine: MachineInfo, content: str, remote_path: str,
    ) -> None:
        """将内容通过 scp 写到远程文件"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            local_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "scp", "-q", "-o", "ConnectTimeout=10",
                local_path,
                f"{machine.user}@{machine.host}:{remote_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace") if stderr else "unknown"
                raise RuntimeError(f"SCP 失败 (exit={proc.returncode}): {err_msg}")
        finally:
            os.unlink(local_path)

    async def _ssh_exec(
        self,
        machine: MachineInfo,
        script: str,
        timeout: int = 600,
    ) -> TaskResult:
        """SSH 执行脚本, 返回 TaskResult

        Bug 12 fix v2: 通过 stdin 管道传输脚本，用 bash -s 执行。
        当 stdin 写完关闭后，bash 收到 EOF，脚本结束后进程自然退出，
        SSH 连接随之干净关闭（避免 FD 泄漏导致 SSH 挂起）。
        """
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-T",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=30",
            f"{machine.user}@{machine.host}",
            "bash -s",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=script.encode("utf-8")), timeout=timeout,
        )

        return TaskResult(
            task_id="",  # 调用方设置
            exit_code=proc.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    # ── 工具方法 ──

    @staticmethod
    def _parse_changed_files(stdout: str, target_dir: str) -> List[str]:
        """从 aider/git 输出中解析变更文件列表"""
        files = []
        for line in stdout.splitlines():
            # aider 输出格式: "Wrote path/to/file.py"
            if line.strip().startswith("Wrote "):
                f = line.strip().replace("Wrote ", "").strip()
                files.append(f)
            # git diff 格式
            elif line.strip().startswith("create mode"):
                parts = line.strip().split()
                if len(parts) >= 3:
                    files.append(parts[-1])

        # 如果没解析到, 返回目标目录
        if not files:
            files = [target_dir]

        return files
