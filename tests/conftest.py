"""
Sirus AI-CRM 测试配置 — conftest.py
提供测试夹具 (fixtures) 供所有测试使用。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import pytest

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def anyio_backend():
    """Select asyncio as the async backend for anyio-based tests."""
    return "asyncio"


@pytest.fixture
def project_root() -> Path:
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture
def sample_task_dict() -> Dict:
    """一个示例任务字典"""
    return {
        "task_id": "T99",
        "target_machine": "4090",
        "target_dir": "crm",
        "description": "测试任务",
        "context_files": ["contracts/crm-api.yaml"],
        "depends_on": [],
        "acceptance": ["通过全部单元测试"],
        "status": "created",
        "retry_count": 0,
        "review_retry": 0,
        "test_retry": 0,
        "fix_instruction": "",
    }


@pytest.fixture
def contracts_dir() -> Path:
    """contracts 目录"""
    return PROJECT_ROOT / "contracts"


@pytest.fixture
def config_path() -> str:
    """orchestrator 配置文件路径"""
    return str(PROJECT_ROOT / "orchestrator" / "config.yaml")
