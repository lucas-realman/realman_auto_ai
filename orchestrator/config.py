"""
Sirus AI-CRM 自动化流水线 — 配置加载器
从 config.yaml + .env 加载并解析配置
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .task_models import MachineInfo

_CONFIG_DIR = Path(__file__).parent
_REPO_ROOT = _CONFIG_DIR.parent


def _expand_env_vars(obj: Any) -> Any:
    """递归展开 ${VAR} 格式的环境变量引用"""
    if isinstance(obj, str):
        def _replace(m):
            var = m.group(1)
            return os.environ.get(var, m.group(0))
        return re.sub(r"\$\{(\w+)\}", _replace, obj)
    if isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_vars(i) for i in obj]
    return obj


class Config:
    """Orchestrator 配置"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(_CONFIG_DIR / "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self._data: Dict[str, Any] = _expand_env_vars(raw)

    # ── 快捷属性 ──

    @property
    def mode(self) -> str:
        return self._data["orchestrator"]["mode"]

    @property
    def current_sprint(self) -> int:
        return self._data["orchestrator"]["current_sprint"]

    @property
    def poll_interval(self) -> int:
        return self._data["orchestrator"]["poll_interval"]

    @property
    def max_concurrent(self) -> int:
        return self._data["orchestrator"].get("max_concurrent", 4)

    @property
    def port(self) -> int:
        return self._data["orchestrator"].get("port", 9500)

    # LLM / aider
    @property
    def openai_api_base(self) -> str:
        return self._data["llm"]["openai_api_base"]

    @property
    def openai_api_key(self) -> str:
        return self._data["llm"]["openai_api_key"]

    @property
    def aider_model(self) -> str:
        return self._data["llm"]["model"]

    @property
    def single_task_timeout(self) -> int:
        return self._data["task"]["single_task_timeout"]

    @property
    def max_retries(self) -> int:
        return self._data["task"]["max_retries"]

    # Git
    @property
    def git_branch(self) -> str:
        return self._data["git"]["branch"]

    @property
    def git_bare_repo(self) -> str:
        return self._data["git"]["bare_repo"]

    # Testing
    @property
    def pytest_args(self) -> str:
        return self._data["testing"].get("pytest_args", "-x -v --tb=short")

    @property
    def pass_threshold(self) -> float:
        return self._data["testing"].get("pass_threshold", 4.0)

    @property
    def report_dir(self) -> str:
        return self._data["testing"].get("report_dir", "reports/")

    # Notification
    @property
    def dingtalk_webhook(self) -> Optional[str]:
        return self._data.get("notification", {}).get("dingtalk_webhook")

    # Paths
    @property
    def task_card_path(self) -> str:
        return self._data["paths"]["task_card"]

    @property
    def design_doc_path(self) -> str:
        return self._data["paths"]["design_doc"]

    @property
    def contracts_dir(self) -> str:
        return self._data["paths"]["contracts_dir"]

    @property
    def log_dir(self) -> str:
        return self._data["paths"].get("log_dir", "logs/")

    # ── 机器列表 ──

    def get_machines(self) -> Dict[str, MachineInfo]:
        """返回所有机器配置"""
        result = {}
        for name, cfg in self._data.get("machines", {}).items():
            key = str(name)  # YAML 可能将纯数字键解析为 int
            result[key] = MachineInfo(
                name=key,
                host=cfg["host"],
                user=cfg["user"],
                work_dir=cfg["work_dir"],
                owned_dirs=cfg.get("owned_dirs", []),
                aider_prefix=cfg.get("aider_prefix", ""),
            )
        return result

    def get_machine(self, name: str) -> MachineInfo:
        machines = self.get_machines()
        if name not in machines:
            raise KeyError(f"未知机器: {name}, 可用: {list(machines.keys())}")
        return machines[name]

    # ── raw 访问 ──

    def get(self, dotpath: str, default: Any = None) -> Any:
        """用点号路径获取配置: config.get('orchestrator.mode')"""
        keys = dotpath.split(".")
        node = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT
