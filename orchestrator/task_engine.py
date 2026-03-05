"""
Sirus AI-CRM 自动化流水线 — 任务引擎
管理任务队列、依赖关系、执行顺序和状态追踪。

当前版本: 内存队列 (v1, 适合单 orchestrator 进程)
后续计划: Redis 持久化 (v2, 支持重启恢复)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Set

from .state_machine import TaskStateMachine
from .task_models import CodingTask, MachineStatus, ReviewResult, TaskResult, TaskStatus, TestResult

log = logging.getLogger("orchestrator.task_engine")


class TaskEngine:
    """
    任务调度引擎:
    - 维护任务列表 + 状态
    - 依赖关系拓扑排序
    - next_batch() 取下一批可并行任务
    - handle_*() 处理各阶段结果
    """

    def __init__(self, max_retries: int = 3, max_concurrent: int = 4):
        self.max_retries = max_retries
        self.max_concurrent = max_concurrent

        # 存储: task_id → (CodingTask, TaskStateMachine)
        self._tasks: OrderedDict[str, tuple] = OrderedDict()
        self._lock = threading.Lock()

        # 机器状态追踪
        self._machine_busy: Dict[str, Optional[str]] = {}  # machine → current task_id

        # 统计
        self.total_dispatched = 0
        self.total_passed = 0
        self.total_failed = 0
        self.total_escalated = 0

    # ── 任务入队 ──

    def enqueue(self, tasks: List[CodingTask]) -> None:
        """批量入队任务"""
        with self._lock:
            for task in tasks:
                if task.task_id in self._tasks:
                    log.warning("任务 %s 已存在, 跳过", task.task_id)
                    continue
                sm = TaskStateMachine(task, max_retries=self.max_retries)
                sm.enqueue()  # CREATED → QUEUED
                self._tasks[task.task_id] = (task, sm)
                log.info("入队: %s → %s (%s)", task.task_id, task.target_machine, task.target_dir)

    def enqueue_single(self, task: CodingTask) -> None:
        self.enqueue([task])

    # ── 取下一批 ──

    def next_batch(self) -> List[CodingTask]:
        """
        取出下一批可并行执行的任务:
        - 状态为 QUEUED
        - 所有 depends_on 已 PASSED
        - 目标机器当前空闲
        - 最多 max_concurrent 个
        """
        with self._lock:
            completed_ids = self._completed_task_ids()
            busy_machines = set(
                m for m, tid in self._machine_busy.items()
                if tid is not None
            )

            batch = []
            for tid, (task, sm) in self._tasks.items():
                if not sm.can_dispatch:
                    continue

                # 检查依赖
                if task.depends_on:
                    if not all(dep in completed_ids for dep in task.depends_on):
                        continue

                # 检查机器空闲
                if task.target_machine in busy_machines:
                    continue

                batch.append(task)
                busy_machines.add(task.target_machine)

                if len(batch) >= self.max_concurrent:
                    break

            return batch

    # ── 分发确认 ──

    def mark_dispatched(self, task_id: str) -> None:
        """标记任务已分发"""
        with self._lock:
            task, sm = self._get(task_id)
            sm.dispatch()  # QUEUED → DISPATCHED
            self._machine_busy[task.target_machine] = task_id
            self.total_dispatched += 1

    # ── 编码完成 ──

    def handle_coding_done(self, task_id: str, result: TaskResult) -> None:
        """aider 执行完成后调用"""
        with self._lock:
            task, sm = self._get(task_id)
            self._release_machine(task.target_machine)

            sm.coding_done(result)
            # coding_done 会根据 result.success 决定 → CODING_DONE 或 → RETRY/ESCALATED

            if sm.is_retryable:
                sm.requeue()  # RETRY → QUEUED

    # ── Review 完成 ──

    def handle_review_done(self, task_id: str, review: ReviewResult) -> None:
        """Review 完成后调用"""
        with self._lock:
            task, sm = self._get(task_id)

            # CODING_DONE → REVIEW
            sm.start_review()
            # REVIEW → TESTING / RETRY / ESCALATED
            sm.review_done(review)

            if review.passed:
                log.info("[%s] Review 通过 (score=%.1f), 进入测试", task_id, review.score)
            else:
                log.info("[%s] Review 失败 (layer=%s), retries=%d/%d",
                         task_id, review.layer, task.total_retries, self.max_retries)
                if sm.is_retryable:
                    sm.requeue()
                elif task.status == TaskStatus.ESCALATED:
                    self.total_escalated += 1

    # ── 测试完成 ──

    def handle_test_done(self, task_id: str, test_result: TestResult) -> None:
        """测试执行完成后调用"""
        with self._lock:
            task, sm = self._get(task_id)

            # TESTING → JUDGING
            sm.test_done(test_result)
            # JUDGING → PASSED / FAILED
            sm.judge(test_result)

            if task.status == TaskStatus.PASSED:
                self.total_passed += 1
                log.info("[%s] ✅ 测试通过! (pass=%d/%d)",
                         task_id, test_result.passed_count, test_result.total)
            elif task.status == TaskStatus.FAILED:
                sm.handle_failure()  # FAILED → RETRY / ESCALATED
                if sm.is_retryable:
                    sm.requeue()
                    log.info("[%s] 测试失败, 重试 %d/%d",
                             task_id, task.total_retries, self.max_retries)
                else:
                    self.total_escalated += 1
                    log.error("[%s] ❌ 测试失败且已达最大重试, 升级人工",
                              task_id)

    # ── 状态查询 ──

    def all_done(self) -> bool:
        """是否所有任务都已结束 (PASSED 或 ESCALATED)"""
        with self._lock:
            return all(
                sm.is_terminal for _, sm in self._tasks.values()
            )

    def get_status_summary(self) -> Dict[str, int]:
        with self._lock:
            counts = {}
            for _, (task, _) in self._tasks.items():
                status = task.status.value
                counts[status] = counts.get(status, 0) + 1
            return counts

    def get_task(self, task_id: str) -> Optional[CodingTask]:
        with self._lock:
            if task_id in self._tasks:
                return self._tasks[task_id][0]
            return None

    def get_all_tasks(self) -> List[CodingTask]:
        with self._lock:
            return [task for task, _ in self._tasks.values()]

    def get_tasks_in_status(self, status: TaskStatus) -> List[CodingTask]:
        with self._lock:
            return [
                task for task, _ in self._tasks.values()
                if task.status == status
            ]

    def get_escalated_tasks(self) -> List[CodingTask]:
        return self.get_tasks_in_status(TaskStatus.ESCALATED)

    @property
    def total_tasks(self) -> int:
        return len(self._tasks)

    @property
    def completed_count(self) -> int:
        return self.total_passed + self.total_escalated

    @property
    def in_progress_count(self) -> int:
        with self._lock:
            return sum(
                1 for task, _ in self._tasks.values()
                if task.status in (
                    TaskStatus.DISPATCHED, TaskStatus.CODING_DONE,
                    TaskStatus.REVIEW, TaskStatus.TESTING, TaskStatus.JUDGING,
                )
            )

    # ── 内部工具 ──

    def _get(self, task_id: str) -> tuple:
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        return self._tasks[task_id]

    def _completed_task_ids(self) -> Set[str]:
        return {
            tid for tid, (task, _) in self._tasks.items()
            if task.status == TaskStatus.PASSED
        }

    def _release_machine(self, machine: str) -> None:
        if machine in self._machine_busy:
            self._machine_busy[machine] = None
