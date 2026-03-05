"""
Sirus AI-CRM 自动化流水线 — 文档解析器
从 docs/07-Sprint任务卡.md 解析出结构化的 CodingTask 列表。

实际任务卡格式 (v2):
  | **W1** | vLLM 部署 | "aider 指令..." | `scripts/start_vllm.sh` | 完成标志 |

机器约定:
  W0=orchestrator, W1=4090, W2=mac_min_8T, W3=gateway, W4=data_center
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .task_models import CodingTask

log = logging.getLogger("orchestrator.doc_parser")

# 机器代号 → config.yaml 中的机器名
MACHINE_ALIAS: Dict[str, str] = {
    "W0": "orchestrator",
    "W1": "4090",
    "W2": "mac_min_8T",
    "W3": "gateway",
    "W4": "data_center",
    "W5": "orchestrator",  # W5 (staging) 已迁至 W0
}

# 机器名 → 默认关联目录
MACHINE_DEFAULT_DIR: Dict[str, str] = {
    "4090": "agent/",
    "mac_min_8T": "crm/",
    "gateway": "deploy/",
    "data_center": "scripts/",
    "orchestrator": "orchestrator/",
}


class DocParser:
    """解析 Sprint 任务卡 + 设计文档 → 生成 CodingTask 列表"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def parse_task_card(
        self,
        card_path: str = "docs/07-Sprint任务卡.md",
        sprint: Optional[int] = None,
    ) -> List[CodingTask]:
        """
        解析任务卡 Markdown 表格，返回 CodingTask 列表。

        实际表格格式:
        | **W1** | 任务名 | "aider 指令" | `产出文件` | 完成标志 |

        Args:
            card_path: 任务卡路径 (相对 repo_root 或绝对路径)
            sprint: 只解析指定 Sprint, None=全部
        """
        full_path = Path(card_path) if Path(card_path).is_absolute() else self.repo_path / card_path
        if not full_path.exists():
            log.error("任务卡不存在: %s", full_path)
            return []

        text = full_path.read_text(encoding="utf-8")

        # 按 Sprint 分段
        if sprint is not None:
            text = self._extract_sprint_section(text, sprint)
            if not text:
                log.warning("未找到 Sprint %s 相关章节", sprint)
                return []

        tasks = self._parse_tables(text)

        log.info("解析到 %d 个任务", len(tasks))
        for t in tasks:
            log.info("  %s → %s [%s] %s",
                     t.task_id, t.target_machine, t.target_dir, t.description[:40])

        return tasks

    def _extract_sprint_section(self, text: str, sprint: int) -> str:
        """提取 '## X. Sprint Y-Z' 到下一个 '## ' 之间的内容"""
        # 匹配 Sprint 编号: sprint=1 → 匹配 "Sprint 1-2" 或 "Sprint 1"
        pattern = rf"^##\s+\d+\.\s+Sprint\s+\d*{sprint}\d*[：:—\-]"
        lines = text.splitlines()
        start = None
        end = len(lines)
        for i, line in enumerate(lines):
            if start is None:
                if re.match(pattern, line):
                    start = i
            elif line.startswith("## ") and not line.startswith("### "):
                end = i
                break
        if start is None:
            return ""
        return "\n".join(lines[start:end])

    def _parse_tables(self, text: str) -> List[CodingTask]:
        """
        解析所有 Day 表格。
        每行格式: | **W1** | 任务名 | "aider指令" | `产出文件` | 完成标志 |
        """
        tasks: List[CodingTask] = []
        current_day = ""
        task_counter = 0

        for line in text.splitlines():
            # 检测 Day 标题: #### Day 1 — 环境搭建
            day_match = re.match(r"^####\s+Day\s+(\d+)", line)
            if day_match:
                current_day = day_match.group(1)
                continue

            # 跳过表头和分隔线
            if re.match(r"\s*\|[-\s|]+\|", line):
                continue
            if re.match(r"\s*\|\s*机器\s*\|", line):
                continue

            # 匹配任务行: | **W1** | 任务 | 指令 | 产出 | 完成标志 |
            # 也匹配: | **W1-W4** | 跨机器任务 | ...
            m = re.match(r"\s*\|\s*\*\*(\w[\w\-]*)\*\*\s*\|", line)
            if not m:
                continue

            machine_code = m.group(1)  # e.g. "W1" or "W1-W4"
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]  # 去空

            if len(parts) < 3:
                continue

            # 解析字段
            task_name = parts[1].strip()
            aider_instruction = parts[2].strip() if len(parts) > 2 else ""
            output_files = parts[3].strip() if len(parts) > 3 else ""
            acceptance = parts[4].strip() if len(parts) > 4 else ""

            # 处理跨机器任务 (W1-W4)
            if "-" in machine_code:
                machines = self._expand_machine_range(machine_code)
            else:
                machines = [machine_code]

            for mc in machines:
                machine_name = MACHINE_ALIAS.get(mc, mc)
                if machine_name == mc and not mc.startswith("W"):
                    # 不是 W 开头也不在别名里，跳过
                    log.warning("未知机器代号: %s, 跳过", mc)
                    continue

                task_counter += 1
                task_id = f"S{current_day}_{mc}" if current_day else f"T{task_counter}"

                # 推断目标目录: 从产出文件提取，否则用机器默认目录
                target_dir = self._infer_target_dir(output_files, machine_name)

                # 清理指令中的引号
                clean_instruction = aider_instruction.strip('"').strip('"').strip('"')

                # 推断上下文文件
                context_files = self._infer_context_files(target_dir)

                tasks.append(CodingTask(
                    task_id=task_id,
                    target_machine=machine_name,
                    target_dir=target_dir,
                    description=f"{task_name}: {clean_instruction}" if clean_instruction else task_name,
                    context_files=context_files,
                    acceptance=[acceptance] if acceptance else [],
                ))

        return tasks

    def _expand_machine_range(self, code: str) -> List[str]:
        """展开 'W1-W4' → ['W1', 'W2', 'W3', 'W4']"""
        m = re.match(r"W(\d+)-W(\d+)", code)
        if not m:
            return [code]
        start, end = int(m.group(1)), int(m.group(2))
        return [f"W{i}" for i in range(start, end + 1)]

    def _infer_target_dir(self, output_files: str, machine_name: str) -> str:
        """从产出文件路径推断目标目录"""
        # 清理 markdown 格式
        clean = output_files.replace("`", "").replace("(更新)", "").strip()
        if clean and "/" in clean:
            # 取第一个文件的目录: "agent/main.py, agent/config.py" → "agent/"
            first_file = clean.split(",")[0].strip()
            parts = first_file.split("/")
            if len(parts) >= 2:
                return parts[0] + "/"
        # 回退到机器默认目录
        return MACHINE_DEFAULT_DIR.get(machine_name, "./")

    def _infer_context_files(self, target_dir: str) -> List[str]:
        """根据目标目录推断 aider 应加载的上下文文件"""
        context = []
        contracts_dir = self.repo_path / "contracts"

        if contracts_dir.exists():
            for f in contracts_dir.iterdir():
                if f.suffix in (".yaml", ".yml", ".sql"):
                    context.append(str(f.relative_to(self.repo_path)))

        # 如果目标目录已有 __init__.py，加载它
        clean_dir = target_dir.rstrip("/")
        init_file = self.repo_path / clean_dir / "__init__.py"
        if init_file.exists():
            context.append(str(init_file.relative_to(self.repo_path)))

        return context

    def _extract_task_detail(self, text: str, task_id: str) -> Optional[str]:
        """提取 ### T{n} 到下一个 ### T 或 --- 之间的详细说明 (兼容旧格式)"""
        capturing = False
        detail_lines = []

        for line in text.splitlines():
            if re.match(rf"^###\s+{re.escape(task_id)}\b", line):
                capturing = True
                continue
            if capturing:
                if re.match(r"^###\s+T\d+", line) or line.strip() == "---":
                    break
                detail_lines.append(line)

        detail = "\n".join(detail_lines).strip()
        return detail if detail else None

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
