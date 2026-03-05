"""
Sirus AI-CRM 自动化流水线 — 任务状态机
实现 docs/08 §2.3 的状态流转图:
  CREATED → QUEUED → DISPATCHED → CODING_DONE → REVIEW
  → TESTING → JUDGING → PASSED / RETRY / ESCALATED
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from .task_models import CodingTask, ReviewResult, TaskResult, TaskStatus, TestResult

log = logging.getLogger("orchestrator.state_machine")

# ── 合法转换表 ──────────────────────────────────────────

_TRANSITIONS = {
    TaskStatus.CREATED:     [TaskStatus.QUEUED],
    TaskStatus.QUEUED:      [TaskStatus.DISPATCHED],
    TaskStatus.DISPATCHED:  [TaskStatus.CODING_DONE, TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.CODING_DONE: [TaskStatus.REVIEW],
    TaskStatus.REVIEW:      [TaskStatus.TESTING, TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.TESTING:     [TaskStatus.JUDGING],
    TaskStatus.JUDGING:     [TaskStatus.PASSED, TaskStatus.FAILED],
    TaskStatus.FAILED:      [TaskStatus.RETRY, TaskStatus.ESCALATED],
    TaskStatus.RETRY:       [TaskStatus.QUEUED],
    # 终态不可转换
    TaskStatus.PASSED:      [],
    TaskStatus.ESCALATED:   [],
}


class StateMachineError(Exception):
    pass


class TaskStateMachine:
    """
    管理单个任务的状态流转。
    所有状态变更都经过此类校验，确保不会出现非法跳转。
    """

    def __init__(self, task: CodingTask, max_retries: int = 3):
        self.task = task
        self.max_retries = max_retries

    def _transit(self, new_status: TaskStatus) -> None:
        old = self.task.status
        allowed = _TRANSITIONS.get(old, [])
        if new_status not in allowed:
            raise StateMachineError(
                f"[{self.task.task_id}] 非法状态转换: {old.value} → {new_status.value}  "
                f"(允许: {[s.value for s in allowed]})"
            )
        self.task.status = new_status
        log.info(f"[{self.task.task_id}] {old.value} → {new_status.value}")

    # ── 便捷方法 ──

    def enqueue(self) -> None:
        """CREATED → QUEUED"""
        self._transit(TaskStatus.QUEUED)

    def dispatch(self) -> None:
        """QUEUED → DISPATCHED"""
        self._transit(TaskStatus.DISPATCHED)
        self.task.started_at = time.time()

    def coding_done(self, result: TaskResult) -> None:
        """DISPATCHED → CODING_DONE (aider 执行成功)"""
        if result.success:
            self._transit(TaskStatus.CODING_DONE)
        else:
            # aider 执行失败
            self.task.last_error = result.stderr or result.stdout
            if self.task.total_retries < self.max_retries:
                self._transit(TaskStatus.RETRY)
            else:
                self._transit(TaskStatus.ESCALATED)

    def start_review(self) -> None:
        """CODING_DONE → REVIEW"""
        self._transit(TaskStatus.REVIEW)

    def review_done(self, review: ReviewResult) -> None:
        """REVIEW → TESTING / RETRY / ESCALATED"""
        if review.passed:
            self._transit(TaskStatus.TESTING)
        else:
            self.task.last_error = "; ".join(review.issues)
            self.task.fix_instruction = review.fix_instruction
            self.task.review_retry += 1
            if self.task.total_retries < self.max_retries:
                self._transit(TaskStatus.RETRY)
            else:
                self._transit(TaskStatus.ESCALATED)

    def start_testing(self) -> None:
        """TESTING 只是标记, 实际动作在 test_runner"""
        pass  # 已经是 TESTING 状态

    def test_done(self, test_result: TestResult) -> None:
        """TESTING → JUDGING"""
        self._transit(TaskStatus.JUDGING)

    def judge(self, test_result: TestResult) -> None:
        """JUDGING → PASSED / FAILED"""
        if test_result.passed:
            self._transit(TaskStatus.PASSED)
            self.task.finished_at = time.time()
        else:
            self._transit(TaskStatus.FAILED)
            self.task.last_error = "\n".join(test_result.failures)

    def handle_failure(self) -> None:
        """FAILED → RETRY / ESCALATED"""
        self.task.test_retry += 1
        # 从 test 失败信息中生成修复指令
        self.task.fix_instruction = (
            f"测试失败 (第 {self.task.test_retry} 次)，错误信息:\n"
            f"{self.task.last_error}\n\n"
            f"请根据以上错误信息修复代码。"
        )
        if self.task.total_retries < self.max_retries:
            self._transit(TaskStatus.RETRY)
        else:
            self._transit(TaskStatus.ESCALATED)

    def requeue(self) -> None:
        """RETRY → QUEUED (重新入队)"""
        self._transit(TaskStatus.QUEUED)
        self.task.retry_count += 1

    # ── 状态查询 ──

    @property
    def is_terminal(self) -> bool:
        return self.task.status in (TaskStatus.PASSED, TaskStatus.ESCALATED)

    @property
    def is_retryable(self) -> bool:
        return self.task.status == TaskStatus.RETRY

    @property
    def is_waiting(self) -> bool:
        return self.task.status == TaskStatus.QUEUED

    @property
    def can_dispatch(self) -> bool:
        return self.task.status == TaskStatus.QUEUED

    @property
    def needs_review(self) -> bool:
        return self.task.status == TaskStatus.CODING_DONE

    @property
    def needs_testing(self) -> bool:
        return self.task.status == TaskStatus.TESTING
