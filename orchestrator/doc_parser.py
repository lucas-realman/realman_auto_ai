"""
Sirus AI-CRM 自动化流水线 — 文档解析器
从 docs/07-Sprint任务卡.md 解析出结构化的 CodingTask 列表。

当前版本: 正则解析 Markdown 表格 (v1)
后续计划: 接入 LLM 智能拆解 (v2)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .task_models import CodingTask

log = logging.getLogger("orchestrator.doc_parser")


class DocParser:
    """解析 Sprint 任务卡 + 设计文档 → 生成 CodingTask 列表"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def parse_task_card(
        self,
        card_path: str = "docs/07-Sprint任务卡.md",
    ) -> List[CodingTask]:
        """
        解析任务卡 Markdown 表格，返回 CodingTask 列表。

        表格格式 (pipeline 分隔):
        | T1 | mac_min_8T (172.16.12.50) | ssh mac_min_8T | CRM `/health` API | `crm/` | 5 min |
        """
        full_path = self.repo_path / card_path
        if not full_path.exists():
            log.error("任务卡不存在: %s", full_path)
            return []

        text = full_path.read_text(encoding="utf-8")

        tasks = self._parse_table(text)
        execution_order = self._parse_execution_order(text)

        # 附加详细说明
        for task in tasks:
            detail = self._extract_task_detail(text, task.task_id)
            if detail:
                task.description = f"{task.description}\n\n{detail}"

        log.info("解析到 %d 个任务, 执行顺序: parallel=%s, serial=%s",
                 len(tasks),
                 execution_order.get("parallel", []),
                 execution_order.get("serial", []))

        return tasks

    def _parse_table(self, text: str) -> List[CodingTask]:
        """解析 Markdown 表格行"""
        tasks = []
        for line in text.splitlines():
            # 匹配 | T1 | machine | ... | desc | dir | time |
            if not re.match(r"\s*\|.*T\d+", line):
                continue

            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]  # 去掉空字符串

            if len(parts) < 5:
                continue

            tid = parts[0].strip()
            if not re.match(r"T\d+", tid):
                continue

            machine = parts[1].strip()
            # 去掉 IP 部分: "mac_min_8T (172.16.12.50)" → "mac_min_8T"
            machine = re.sub(r"\s*\(.*?\)", "", machine).strip()

            desc = parts[3].strip().replace("`", "")
            target_dir = parts[4].strip().replace("`", "")

            # 为每个目录推断 context_files
            context_files = self._infer_context_files(target_dir)

            tasks.append(CodingTask(
                task_id=tid,
                target_machine=machine,
                target_dir=target_dir,
                description=desc,
                context_files=context_files,
            ))

        return tasks

    def _parse_execution_order(self, text: str) -> Dict[str, List[str]]:
        """从 '执行顺序' 节解析并行/串行分组"""
        result = {"parallel": [], "serial": []}
        in_order = False

        for line in text.splitlines():
            if "执行顺序" in line:
                in_order = True
                continue
            if not in_order:
                continue
            if line.startswith("##") and "执行顺序" not in line:
                break

            tids = re.findall(r"T\d+", line)
            if not tids:
                continue

            if "并行" in line:
                result["parallel"].extend(tids)
            elif "串行" in line:
                # 串行行只取第一个 T[n]
                result["serial"].append(tids[0])

        return result

    def _extract_task_detail(self, text: str, task_id: str) -> Optional[str]:
        """提取 ### T{n} 到下一个 ### T 或 --- 之间的详细说明"""
        capturing = False
        detail_lines = []

        for line in text.splitlines():
            # 匹配 ### T1 开头 (后面可能有空格和标题文字)
            if re.match(rf"^###\s+{re.escape(task_id)}\b", line):
                capturing = True
                continue

            if capturing:
                # 遇到下一个 ### T 或 --- 停止
                if re.match(r"^###\s+T\d+", line) or line.strip() == "---":
                    break
                detail_lines.append(line)

        detail = "\n".join(detail_lines).strip()
        return detail if detail else None

    def _infer_context_files(self, target_dir: str) -> List[str]:
        """根据目标目录推断 aider 应加载的上下文文件"""
        context = []
        contracts_dir = self.repo_path / "contracts"

        if contracts_dir.exists():
            for f in contracts_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".sql"):
                    context.append(str(f.relative_to(self.repo_path)))

        # 如果目标目录已有 __init__.py，加载它
        init_file = self.repo_path / target_dir / "__init__.py"
        if init_file.exists():
            context.append(str(init_file.relative_to(self.repo_path)))

        return context

    def read_contracts(self) -> str:
        """读取所有契约文件内容, 用于 aider --read"""
        contracts_dir = self.repo_path / "contracts"
        if not contracts_dir.exists():
            return ""

        parts = []
        for f in sorted(contracts_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".sql"):
                parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")

        return "\n\n".join(parts)
