"""
Sirus AI-CRM 自动化流水线 — Git 操作工具
提供通用 Git pull / push / tag / commit 功能。
对应 docs/08 §5 "Git 自动化"。
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from .config import Config

log = logging.getLogger("orchestrator.git_ops")


class GitOps:
    """在 orchestrator 本地 repo 执行 Git 操作"""

    def __init__(self, config: Config):
        self.config = config
        self.repo_root = config.repo_root
        self.branch = config.git_branch

    # ── Pull ──

    def pull(self, rebase: bool = True) -> bool:
        """拉取远端最新代码"""
        cmd = ["git", "pull"]
        if rebase:
            cmd.append("--rebase")
        cmd += ["origin", self.branch]
        ok, out = self._run(cmd)
        if not ok:
            log.warning("git pull 失败: %s", out)
        return ok

    # ── Add + Commit ──

    def add_all(self) -> bool:
        ok, _ = self._run(["git", "add", "-A"])
        return ok

    def commit(self, message: str) -> bool:
        """提交已暂存的更改"""
        ok, out = self._run(["git", "commit", "-m", message])
        if not ok:
            if "nothing to commit" in out:
                log.info("没有待提交的更改")
                return True
            log.warning("git commit 失败: %s", out)
        return ok

    # ── Push ──

    def push(self) -> bool:
        """推送到 origin"""
        ok, out = self._run(["git", "push", "origin", self.branch])
        if not ok:
            log.warning("git push 失败: %s", out)
        return ok

    def push_all_remotes(self) -> None:
        """推送到所有配置的 remote"""
        ok, out = self._run(["git", "remote"])
        if not ok:
            return
        remotes = [r.strip() for r in out.splitlines() if r.strip()]
        for remote in remotes:
            ok2, _ = self._run(["git", "push", remote, self.branch])
            if ok2:
                log.info("已推送到 %s", remote)
            else:
                log.warning("推送到 %s 失败", remote)

    # ── Tag ──

    def tag_sprint(self, sprint_id: str) -> bool:
        """为当前 Sprint 打标签 (如 sprint-1-done)"""
        tag = f"sprint-{sprint_id}-done"
        ok, out = self._run(["git", "tag", "-a", tag, "-m", f"Sprint {sprint_id} 完成"])
        if not ok:
            if "already exists" in out:
                log.info("标签 %s 已存在", tag)
                return True
            log.warning("git tag 失败: %s", out)
            return False
        # 推送标签
        ok2, _ = self._run(["git", "push", "origin", tag])
        return ok2

    # ── Sync Nodes (通知各节点 pull) ──

    def sync_nodes(self) -> dict:
        """
        通过 SSH 让各节点执行 git pull。
        返回 {machine_name: success_bool}
        """
        results = {}
        for name, machine in self.config.get_machines().items():
            # 跳过 orchestrator 自身
            if machine.host in ("localhost", "127.0.0.1"):
                continue
            cmd = [
                "ssh", "-o", "ConnectTimeout=10",
                "-o", "StrictHostKeyChecking=no",
                f"{machine.user}@{machine.host}",
                f"cd {machine.work_dir} && git pull origin {self.branch}"
            ]
            ok, out = self._run(cmd, timeout=30)
            results[name] = ok
            if ok:
                log.info("节点 %s 已同步", name)
            else:
                log.warning("节点 %s 同步失败: %s", name, out)
        return results

    # ── 查询 ──

    def get_latest_commit(self) -> str:
        """获取最新 commit 短 hash"""
        ok, out = self._run(["git", "rev-parse", "--short", "HEAD"])
        return out.strip() if ok else "unknown"

    def get_changed_files(self, since_commit: Optional[str] = None) -> List[str]:
        """获取自某个 commit 以来变更的文件列表"""
        if since_commit:
            cmd = ["git", "diff", "--name-only", since_commit, "HEAD"]
        else:
            cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        ok, out = self._run(cmd)
        if not ok:
            return []
        return [f.strip() for f in out.splitlines() if f.strip()]

    def get_log_oneline(self, n: int = 10) -> str:
        """获取最近 N 条 commit 记录"""
        ok, out = self._run(
            ["git", "log", f"--oneline", f"-{n}"]
        )
        return out if ok else ""

    # ── 内部方法 ──

    def _run(
        self,
        cmd: List[str],
        timeout: int = 60,
    ) -> tuple:
        """执行命令, 返回 (success, output)"""
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return (proc.returncode == 0, output)
        except subprocess.TimeoutExpired:
            return (False, f"命令超时 (>{timeout}s)")
        except Exception as e:
            return (False, str(e))
