#!/usr/bin/env python3
"""集成验证: 检查所有 orchestrator 模块能否正确导入"""
import sys
sys.path.insert(0, '.')

modules = [
    ("task_models", "from orchestrator.task_models import TaskStatus, CodingTask, TaskResult, ReviewResult, TestResult, MachineInfo"),
    ("state_machine", "from orchestrator.state_machine import TaskStateMachine"),
    ("config", "from orchestrator.config import Config"),
    ("doc_parser", "from orchestrator.doc_parser import DocParser"),
    ("task_engine", "from orchestrator.task_engine import TaskEngine"),
    ("dispatcher", "from orchestrator.dispatcher import Dispatcher"),
    ("reviewer", "from orchestrator.reviewer import AutoReviewer"),
    ("test_runner", "from orchestrator.test_runner import TestRunner"),
    ("git_ops", "from orchestrator.git_ops import GitOps"),
    ("reporter", "from orchestrator.reporter import Reporter"),
    ("main", "from orchestrator.main import Orchestrator"),
]

ok_count = 0
for name, stmt in modules:
    try:
        exec(stmt)
        print(f"  OK  {name}")
        ok_count += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")

print(f"\n=== {ok_count}/{len(modules)} 模块导入成功 ===")
sys.exit(0 if ok_count == len(modules) else 1)
