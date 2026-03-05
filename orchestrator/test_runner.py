"""
Sirus AI-CRM 自动化流水线 — 测试执行器
在 orchestrator 本地执行 pytest, 收集测试结果。
对应 docs/08 §4.5 "Review + 测试完整闭环"。
"""
from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from .config import Config
from .task_models import CodingTask, TestResult

log = logging.getLogger("orchestrator.test_runner")


class TestRunner:
    """
    在 orchestrator 本机执行 pytest。
    流程: git pull → pytest → 解析结果 → 返回 TestResult
    """

    def __init__(self, config: Config):
        self.config = config
        self.repo_root = config.repo_root

    async def run_tests(
        self,
        task: Optional[CodingTask] = None,
        test_paths: Optional[List[str]] = None,
    ) -> TestResult:
        """
        运行 pytest 测试。

        如果指定 task, 会尝试只运行与 task.target_dir 相关的测试。
        如果指定 test_paths, 只运行这些路径。
        否则运行全部 tests/ 目录。
        """
        start = time.time()

        # 先 pull 最新代码
        self._git_pull()

        # 确定测试路径
        if test_paths:
            paths = test_paths
        elif task:
            paths = self._find_tests_for_task(task)
        else:
            paths = ["tests/"]

        # 检查是否有测试文件
        has_tests = False
        for p in paths:
            test_path = self.repo_root / p
            if test_path.is_file():
                has_tests = True
                break
            if test_path.is_dir():
                for f in test_path.rglob("test_*.py"):
                    has_tests = True
                    break
        if not has_tests:
            log.warning("没有找到测试文件, 跳过测试 (降级通过)")
            return TestResult(
                passed=True,
                total=0, passed_count=0, failed_count=0,
                duration_sec=time.time() - start,
                stdout="[SKIP] 没有测试文件",
            )

        # 构建 pytest 命令
        pytest_args = self.config.pytest_args.split()
        json_report = self.repo_root / "reports" / "pytest_result.json"
        json_report.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "python", "-m", "pytest",
            *pytest_args,
            f"--json-report-file={json_report}",
            "--json-report",
            *paths,
        ]

        log.info("执行: %s", " ".join(cmd))

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                duration_sec=time.time() - start,
                stdout="pytest 执行超时 (>300s)",
                failures=["pytest 超时"],
            )
        except FileNotFoundError:
            # 如果 pytest-json-report 未安装, 降级到普通 pytest
            log.warning("pytest-json-report 未安装, 降级执行")
            return await self._run_plain_pytest(paths, start)

        duration = time.time() - start

        # 解析 JSON 报告
        if json_report.exists():
            return self._parse_json_report(json_report, proc.stdout, duration)

        # 降级: 从 pytest 输出解析
        return self._parse_pytest_output(proc, duration)

    async def _run_plain_pytest(
        self, paths: List[str], start_time: float,
    ) -> TestResult:
        """不带 json-report 的降级执行"""
        cmd = [
            "python", "-m", "pytest",
            "-x", "-v", "--tb=short",
            *paths,
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                duration_sec=time.time() - start_time,
                failures=["pytest 超时"],
            )

        return self._parse_pytest_output(proc, time.time() - start_time)

    # ── 测试路径发现 ──

    def _find_tests_for_task(self, task: CodingTask) -> List[str]:
        """根据任务目标目录推断对应的测试文件路径"""
        tests_dir = self.repo_root / "tests"
        target = task.target_dir.rstrip("/").replace("/", "_")

        candidates = [
            f"tests/test_{target}.py",               # tests/test_crm.py
            f"tests/test_{target}/",                  # tests/test_crm/
            f"tests/{target}/",                       # tests/crm/
        ]

        found = []
        for c in candidates:
            path = self.repo_root / c
            if path.exists():
                found.append(c)

        # 没找到特定测试, 运行全部
        if not found:
            found = ["tests/"]

        return found

    # ── Git ──

    def _git_pull(self) -> None:
        """拉取最新代码"""
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "origin", self.config.git_branch],
                cwd=str(self.repo_root),
                capture_output=True,
                timeout=60,
            )
        except Exception as e:
            log.warning("git pull 失败: %s", e)

    # ── 结果解析 ──

    def _parse_json_report(
        self, report_path: Path, stdout: str, duration: float,
    ) -> TestResult:
        """解析 pytest-json-report 生成的 JSON"""
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("解析 JSON 报告失败: %s", e)
            return TestResult(passed=False, duration_sec=duration, stdout=stdout)

        summary = data.get("summary", {})
        total = summary.get("total", 0)
        passed_count = summary.get("passed", 0)
        failed_count = summary.get("failed", 0)
        error_count = summary.get("error", 0)

        failures = []
        for test in data.get("tests", []):
            if test.get("outcome") in ("failed", "error"):
                nodeid = test.get("nodeid", "?")
                msg = ""
                call = test.get("call", {})
                if call:
                    crash = call.get("crash", {})
                    msg = crash.get("message", "")
                failures.append(f"{nodeid}: {msg}")

        return TestResult(
            passed=(failed_count == 0 and error_count == 0),
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            duration_sec=duration,
            failures=failures,
            stdout=stdout,
        )

    def _parse_pytest_output(
        self, proc: subprocess.CompletedProcess, duration: float,
    ) -> TestResult:
        """从 pytest 标准输出解析结果 (降级方案)"""
        import re

        output = proc.stdout + "\n" + proc.stderr
        passed = proc.returncode == 0

        # 解析 "X passed, Y failed, Z error"
        total = 0
        passed_count = 0
        failed_count = 0
        error_count = 0

        m = re.search(r"(\d+) passed", output)
        if m:
            passed_count = int(m.group(1))
            total += passed_count

        m = re.search(r"(\d+) failed", output)
        if m:
            failed_count = int(m.group(1))
            total += failed_count

        m = re.search(r"(\d+) error", output)
        if m:
            error_count = int(m.group(1))
            total += error_count

        # 提取失败信息
        failures = []
        for line in output.splitlines():
            if line.strip().startswith("FAILED ") or "ERROR " in line:
                failures.append(line.strip())

        return TestResult(
            passed=passed,
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            duration_sec=duration,
            failures=failures,
            stdout=output,
        )
