"""
Sirus AI-CRM 自动化流水线 — 数据模型
定义 CodingTask / TaskResult / ReviewResult 等核心数据结构
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── 任务状态枚举 ──────────────────────────────────────────

class TaskStatus(enum.Enum):
    """任务状态机 (对照 docs/08 §2.3 状态图)"""
    CREATED     = "created"       # 刚从文档解析出来
    QUEUED      = "queued"        # 已入队 (依赖未满足时在此等待)
    DISPATCHED  = "dispatched"    # 已分发到目标机器
    CODING_DONE = "coding_done"   # aider 编码完成
    REVIEW      = "review"        # 进入自动 Review
    TESTING     = "testing"       # 进入自动测试
    JUDGING     = "judging"       # 判定中
    PASSED      = "passed"        # 通过
    FAILED      = "failed"        # 测试失败 (可重试)
    RETRY       = "retry"         # 带修复指令重新排队
    ESCALATED   = "escalated"     # 升级人工


class ReviewLayer(enum.Enum):
    STATIC   = "static"    # Layer 1: py_compile + ruff
    CONTRACT = "contract"  # Layer 2: 契约对齐
    DESIGN   = "design"    # Layer 3: 设计符合度


class MachineStatus(enum.Enum):
    IDLE    = "idle"
    BUSY    = "busy"
    DOWN    = "down"


# ── 核心模型 ──────────────────────────────────────────────

@dataclass
class CodingTask:
    """一个编码任务 (对应任务卡中的一行)"""
    task_id: str                                 # e.g. "T1", "S1-D3-W1-001"
    target_machine: str                          # e.g. "4090", "mac_min_8T"
    target_dir: str                              # e.g. "crm/", "agent/"
    description: str                             # 任务说明
    context_files: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)

    # 运行时状态
    status: TaskStatus = TaskStatus.CREATED
    retry_count: int = 0
    review_retry: int = 0
    test_retry: int = 0
    fix_instruction: Optional[str] = None        # Review/测试失败后的修复指令
    last_error: Optional[str] = None

    # 时间戳
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def total_retries(self) -> int:
        return self.review_retry + self.test_retry

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "task_id": self.task_id,
            "target_machine": self.target_machine,
            "target_dir": self.target_dir,
            "description": self.description,
            "context_files": self.context_files,
            "depends_on": self.depends_on,
            "acceptance": self.acceptance,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "review_retry": self.review_retry,
            "test_retry": self.test_retry,
            "fix_instruction": self.fix_instruction,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CodingTask":
        d = dict(d)
        d["status"] = TaskStatus(d.get("status", "created"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskResult:
    """aider 编码执行结果"""
    task_id: str
    exit_code: int = 1
    stdout: str = ""
    stderr: str = ""
    files_changed: List[str] = field(default_factory=list)
    duration_sec: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class ReviewResult:
    """自动 Review 结果"""
    passed: bool
    layer: Optional[str] = None        # "static" / "contract" / "design"
    issues: List[str] = field(default_factory=list)
    fix_instruction: Optional[str] = None
    score: float = 0.0                  # 0-5, Layer 3 设计评分
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestResult:
    """pytest 测试结果"""
    passed: bool
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    duration_sec: float = 0.0
    failures: List[str] = field(default_factory=list)   # 失败的 case 名称 + 错误信息
    stdout: str = ""


@dataclass
class MachineInfo:
    """远程机器信息"""
    name: str               # e.g. "4090"
    host: str               # e.g. "172.16.11.194"
    user: str               # e.g. "user"
    work_dir: str           # e.g. "~/ai-crm"
    owned_dirs: List[str] = field(default_factory=list)
    aider_prefix: str = ""  # 激活 aider 的 shell 前缀
    status: MachineStatus = MachineStatus.IDLE
    current_task: Optional[str] = None
