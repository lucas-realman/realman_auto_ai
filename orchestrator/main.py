"""
Sirus AI-CRM 自动化流水线 — 主编排器
这是整个流水线的 "大脑", 实现持续自动驱动的闭环引擎。

核心循环:
  解析任务 → 分发编码 → 审查 → 测试 → 判定 → (重试/通过/升级) → 报告

对应 docs/08 §1-§6 完整流水线设计。

用法:
  python -m orchestrator.main                    # 运行当前 Sprint
  python -m orchestrator.main --mode continuous   # 持续模式
  python -m orchestrator.main --dry-run           # 只解析任务, 不执行
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.config import Config
from orchestrator.dispatcher import Dispatcher
from orchestrator.doc_parser import DocParser
from orchestrator.git_ops import GitOps
from orchestrator.reporter import Reporter
from orchestrator.reviewer import AutoReviewer
from orchestrator.state_machine import TaskStateMachine
from orchestrator.task_engine import TaskEngine
from orchestrator.task_models import (
    CodingTask,
    TaskResult,
    TaskStatus,
)
from orchestrator.test_runner import TestRunner

log = logging.getLogger("orchestrator.main")


class Orchestrator:
    """
    持续自动驱动的闭环流水线编排器。

    与 dispatch.sh 的区别:
    - dispatch.sh 是 "单轮批量发射器": 发出去就结束
    - Orchestrator 是 "持续闭环引擎": 编码 → 审查 → 测试 → 判定 → 重试/通过

    解决用户指出的两个核心问题:
    1. "开发并没有完成测试" → 内置 test_runner + reviewer
    2. "阶段目标没有自动化推进" → 主循环自动推进状态直到终态
    """

    def __init__(self, config: Config):
        self.config = config
        self.engine = TaskEngine(
            max_retries=config.max_retries,
            max_concurrent=config.max_concurrent,
        )
        self.dispatcher = Dispatcher(config)
        self.reviewer = AutoReviewer(config)
        self.test_runner = TestRunner(config)
        self.git_ops = GitOps(config)
        self.reporter = Reporter(config)
        self.doc_parser = DocParser(str(config.repo_root))

    # ── 主入口 ──

    async def run_sprint(self, dry_run: bool = False) -> bool:
        """
        执行一个 Sprint 的完整自动化流程。

        Returns:
            True = Sprint 全部通过, False = 有任务失败/升级
        """
        sprint_id = self.config.current_sprint
        log.info("=" * 60)
        log.info("Sprint %s 开始", sprint_id)
        log.info("=" * 60)

        # Step 1: 解析任务
        task_card_path = self.config.task_card_path
        if not Path(task_card_path).is_absolute():
            task_card_path = str(self.config.repo_root / task_card_path)

        tasks = self.doc_parser.parse_task_card(task_card_path)
        if not tasks:
            log.error("未解析到任何任务, 退出")
            await self.reporter.notify_error("未解析到任何任务")
            return False

        log.info("解析到 %d 个任务", len(tasks))
        for t in tasks:
            log.info("  %s → %s (%s)", t.task_id, t.target_machine, t.description[:40])

        if dry_run:
            log.info("[DRY RUN] 只解析, 不执行")
            return True

        # Step 2: 入队
        self.engine.enqueue(tasks)

        # Step 3: 通知开始
        await self.reporter.notify_sprint_start(sprint_id, tasks)

        # Step 4: 主循环 — 持续驱动直到所有任务终态
        success = await self._main_loop()

        # Step 5: 后置处理
        await self._finalize(sprint_id, tasks, success)

        return success

    async def run_continuous(self) -> None:
        """
        持续模式: 监听新任务, 自动解析执行。
        (简化实现: 定期扫描任务卡变化)
        """
        log.info("持续模式启动, 每 %ds 检查", self.config.poll_interval)
        last_mtime = 0.0
        while True:
            task_card_path = self.config.task_card_path
            if not Path(task_card_path).is_absolute():
                task_card_path = str(self.config.repo_root / task_card_path)

            try:
                mtime = Path(task_card_path).stat().st_mtime
            except FileNotFoundError:
                mtime = 0.0

            if mtime > last_mtime:
                log.info("检测到任务卡更新, 启动 Sprint")
                last_mtime = mtime
                await self.run_sprint()

            await asyncio.sleep(self.config.poll_interval)

    # ── 核心循环 ──

    async def _main_loop(self) -> bool:
        """
        核心驱动循环。

        每轮:
          1. 取出可分发的批次
          2. 并行分发到远程机器 (aider)
          3. 收集编码结果
          4. 审查 (三层)
          5. 测试
          6. 判定 (通过/重试/升级)
          7. 检查是否全部完成
        """
        max_rounds = 20  # 防无限循环
        round_num = 0

        while not self.engine.all_done() and round_num < max_rounds:
            round_num += 1
            log.info("── 第 %d 轮 ──", round_num)

            # 1) 取出可分发的批次
            batch = self.engine.next_batch()
            if not batch:
                # 可能有任务在等待依赖, 或已在 review/test 中
                pending = self._get_pending_tasks()
                if pending:
                    log.info("等待中的任务: %s", [t.task_id for t in pending])
                    log.info("等待 %ds 后重试...", self.config.poll_interval)
                    await asyncio.sleep(self.config.poll_interval)
                    continue
                else:
                    log.info("没有更多可分发任务, 退出循环")
                    break

            log.info("本轮分发 %d 个任务: %s",
                     len(batch), [t.task_id for t in batch])

            # 2) 标记分发 & 通知
            for task in batch:
                self.engine.mark_dispatched(task.task_id)
                await self.reporter.notify_task_dispatched(task)

            # 3) 并行分发到远程, 收集编码结果
            results = await self.dispatcher.dispatch_batch(batch)

            # 4) 处理每个任务的编码结果
            for task, result in zip(batch, results):
                await self._process_task_result(task, result)

            # 小间隔, 避免过快循环
            await asyncio.sleep(2)

        all_ok = self.engine.all_done()
        if round_num >= max_rounds:
            log.warning("达到最大轮次 (%d), 强制结束", max_rounds)
            await self.reporter.notify_error(f"达到最大轮次 {max_rounds}, 强制结束")

        return all_ok

    async def _process_task_result(
        self,
        task: CodingTask,
        result: TaskResult,
    ) -> None:
        """
        处理单个任务的编码结果, 驱动完整状态转换:
        coding_done → review → test → judge
        """
        sm = TaskStateMachine(task)

        # ── 编码结果 ──
        sm.coding_done(result)
        self.engine.handle_coding_done(task.task_id, result)
        log.info("[%s] 编码完成: exit=%d, duration=%.1fs",
                 task.task_id, result.exit_code, result.duration_sec)

        if result.exit_code != 0:
            log.warning("[%s] 编码失败, 进入重试判定", task.task_id)
            self._handle_judge(sm)
            await self.reporter.notify_task_result(task)
            return

        # ── Git Pull (orchestrator 侧) ──
        self.git_ops.pull()

        # ── 审查 ──
        sm.start_review()
        review = await self.reviewer.review(task, result)
        sm.review_done(review)
        self.engine.handle_review_done(task.task_id, review)
        log.info("[%s] 审查完成: passed=%s, layer=%s",
                 task.task_id, review.passed, review.layer)

        if not review.passed:
            log.info("[%s] 审查未通过, 进入重试", task.task_id)
            self._handle_judge(sm)
            await self.reporter.notify_task_result(task, review=review)
            return

        # ── 测试 ──
        test = await self.test_runner.run_tests(task=task)
        sm.test_done(test)
        self.engine.handle_test_done(task.task_id, test)
        log.info("[%s] 测试完成: passed=%s, %d/%d",
                 task.task_id, test.passed, test.passed_count, test.total)

        if not test.passed:
            log.info("[%s] 测试未通过, 进入重试", task.task_id)
            self._handle_judge(sm)
            await self.reporter.notify_task_result(task, review=review, test=test)
            return

        # ── 通过 ──
        sm.judge(test)  # JUDGING → PASSED
        log.info("[%s] ✅ 任务通过!", task.task_id)
        await self.reporter.notify_task_result(task, review=review, test=test)

    def _handle_judge(self, sm: TaskStateMachine) -> None:
        """判定: 是否重试 or 升级"""
        task = sm.task
        max_retry = self.config.get("task.max_retries", 3)

        total_retry = task.retry_count + task.review_retry + task.test_retry
        if total_retry < max_retry:
            # 可重试 → 重新入队
            sm.handle_failure()
            sm.requeue()
            self.engine.enqueue_single(task)
            log.info("[%s] 重新入队 (第 %d 次重试)", task.task_id, total_retry + 1)
        else:
            # 超过重试上限 → 升级
            sm.handle_failure()
            task.status = TaskStatus.ESCALATED
            log.warning("[%s] 超过重试上限, 升级为人工处理", task.task_id)

    def _get_pending_tasks(self) -> List[CodingTask]:
        """获取非终态、非已分发的任务"""
        pending = []
        for task, _sm in self.engine._tasks.values():
            if task.status not in (
                TaskStatus.PASSED, TaskStatus.FAILED,
                TaskStatus.ESCALATED, TaskStatus.DISPATCHED,
            ):
                pending.append(task)
        return pending

    # ── 后置处理 ──

    async def _finalize(
        self,
        sprint_id: str,
        tasks: List[CodingTask],
        success: bool,
    ) -> None:
        """Sprint 后置处理: 报告、标签、同步"""
        # 获取统计
        summary = self.engine.get_status_summary()

        # 保存本地报告
        self.reporter.save_sprint_report(sprint_id, tasks, summary)

        # 发送完成通知
        await self.reporter.notify_sprint_done(sprint_id, tasks)

        # 如果全部通过, 打标签
        if success:
            self.git_ops.tag_sprint(sprint_id)
            log.info("Sprint %s 已打标签", sprint_id)

        # 同步各节点
        sync_results = self.git_ops.sync_nodes()
        log.info("节点同步结果: %s", sync_results)

        log.info("=" * 60)
        log.info("Sprint %s %s", sprint_id, "全部通过 ✅" if success else "有失败 ❌")
        log.info("=" * 60)


# ── CLI 入口 ──

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sirus AI-CRM 自动化流水线编排器",
    )
    parser.add_argument(
        "--config", "-c",
        default=str(PROJECT_ROOT / "orchestrator" / "config.yaml"),
        help="配置文件路径",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["sprint", "continuous"],
        default="sprint",
        help="运行模式: sprint (单次) / continuous (持续)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只解析任务, 不执行",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    log.info("加载配置: %s", args.config)
    config = Config(args.config)

    orchestrator = Orchestrator(config)

    if args.mode == "continuous":
        await orchestrator.run_continuous()
        return 0
    else:
        success = await orchestrator.run_sprint(dry_run=args.dry_run)
        return 0 if success else 1


def main() -> None:
    exit_code = asyncio.run(async_main())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
