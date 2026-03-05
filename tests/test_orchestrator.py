"""
Sirus AI-CRM 测试 — Orchestrator 核心模块单元测试
验证 task_models, state_machine, task_engine, doc_parser 基础功能。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保导入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.task_models import (
    CodingTask,
    MachineInfo,
    MachineStatus,
    ReviewLayer,
    ReviewResult,
    TaskResult,
    TaskStatus,
    TestResult,
)
from orchestrator.state_machine import TaskStateMachine, StateMachineError


# ───────── TaskModels ─────────

class TestTaskStatus:
    def test_all_statuses(self):
        """确保所有预定义状态存在"""
        expected = [
            "created", "queued", "dispatched", "coding_done",
            "review", "testing", "judging", "passed", "failed",
            "retry", "escalated",
        ]
        for val in expected:
            assert TaskStatus(val) is not None

    def test_status_value(self):
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.PASSED.value == "passed"


class TestCodingTask:
    def test_create_minimal(self):
        task = CodingTask(
            task_id="T1",
            target_machine="4090",
            target_dir="crm",
            description="测试",
        )
        assert task.task_id == "T1"
        assert task.status == TaskStatus.CREATED
        assert task.retry_count == 0

    def test_to_dict_and_back(self, sample_task_dict):
        task = CodingTask(
            task_id=sample_task_dict["task_id"],
            target_machine=sample_task_dict["target_machine"],
            target_dir=sample_task_dict["target_dir"],
            description=sample_task_dict["description"],
            context_files=sample_task_dict["context_files"],
        )
        d = task.to_dict()
        assert d["task_id"] == "T99"
        assert d["status"] == "created"

        task2 = CodingTask.from_dict(d)
        assert task2.task_id == task.task_id
        assert task2.target_machine == task.target_machine

    def test_task_result(self):
        r = TaskResult(
            task_id="T1",
            exit_code=0,
            stdout="ok",
            stderr="",
            files_changed=["crm/api.py"],
            duration_sec=10.5,
        )
        assert r.exit_code == 0
        assert len(r.files_changed) == 1

    def test_review_result(self):
        r = ReviewResult(
            passed=True,
            layer=ReviewLayer.STATIC,
            issues=[],
        )
        assert r.passed
        assert r.layer == ReviewLayer.STATIC

    def test_test_result(self):
        r = TestResult(passed=True, total=5, passed_count=5)
        assert r.failed_count == 0


# ───────── StateMachine ─────────

class TestStateMachine:
    def _make_task(self) -> CodingTask:
        return CodingTask(
            task_id="T1",
            target_machine="4090",
            target_dir="crm",
            description="测试任务",
        )

    def test_happy_path(self):
        """完整通过路径: created → queued → dispatched → coding_done → review → testing → judging → passed"""
        task = self._make_task()
        sm = TaskStateMachine(task)

        sm.enqueue()
        assert task.status == TaskStatus.QUEUED

        sm.dispatch()
        assert task.status == TaskStatus.DISPATCHED

        result = TaskResult(task_id="T1", exit_code=0, stdout="ok")
        sm.coding_done(result)
        assert task.status == TaskStatus.CODING_DONE

        sm.start_review()
        assert task.status == TaskStatus.REVIEW

        review = ReviewResult(passed=True, layer="static", issues=[])
        sm.review_done(review)
        assert task.status == TaskStatus.TESTING

        test_result = TestResult(passed=True, total=5, passed_count=5)
        sm.test_done(test_result)
        assert task.status == TaskStatus.JUDGING

        sm.judge(test_result)
        assert task.status == TaskStatus.PASSED
        assert sm.is_terminal

    def test_review_fail_retry(self):
        """审查失败 → RETRY → 重新入队"""
        task = self._make_task()
        sm = TaskStateMachine(task)

        sm.enqueue()
        sm.dispatch()
        sm.coding_done(TaskResult(task_id="T1", exit_code=0, stdout="ok"))
        sm.start_review()

        review = ReviewResult(
            passed=False,
            layer="contract",
            issues=["缺少必要的 API 路由"],
            fix_instruction="请实现 /api/v1/customers GET 路由",
        )
        sm.review_done(review)
        # 审查失败 → 直接到 RETRY (review_done 内部判定)
        assert task.status == TaskStatus.RETRY
        assert task.fix_instruction == "请实现 /api/v1/customers GET 路由"

        sm.requeue()
        assert task.status == TaskStatus.QUEUED

    def test_terminal_states(self):
        """PASSED 和 ESCALATED 是终态; FAILED 不是 (可以 retry)"""
        task = self._make_task()
        task.status = TaskStatus.PASSED
        sm = TaskStateMachine(task)
        assert sm.is_terminal

        task.status = TaskStatus.ESCALATED
        assert sm.is_terminal

        # FAILED 不是终态, 可以 retry 或 escalate
        task.status = TaskStatus.FAILED
        assert not sm.is_terminal

    def test_illegal_transition(self):
        """非法状态转换应抛出 StateMachineError"""
        task = self._make_task()
        sm = TaskStateMachine(task)
        # 从 CREATED 不能直接 dispatch (需要先 enqueue)
        with pytest.raises(StateMachineError):
            sm.dispatch()


class TestMachineInfo:
    def test_create(self):
        m = MachineInfo(
            name="test",
            host="192.168.1.1",
            user="testuser",
            work_dir="/home/test/project",
            owned_dirs=["crm", "agent"],
            aider_prefix="export PATH=$HOME/.local/bin:$PATH",
        )
        assert m.name == "test"
        assert m.status == MachineStatus.IDLE
        assert len(m.owned_dirs) == 2
