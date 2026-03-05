"""
Sirus AI-CRM 验收测试生成器
从 docs/07-Sprint任务卡.md 的「完成标志」列解析验收标准，
分析测试类型分布，可选生成 pytest 测试骨架。

用法:
    python3 -m orchestrator.acceptance_generator                    # 分析全部
    python3 -m orchestrator.acceptance_generator --sprint 1-2       # 指定 Sprint
    python3 -m orchestrator.acceptance_generator --report           # 输出 Markdown 报告
    python3 -m orchestrator.acceptance_generator --generate         # 生成测试骨架
"""
from __future__ import annotations

import argparse
import logging
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("orchestrator.acceptance_generator")

# ── 机器映射 ──

MACHINE_MAP = {
    "W0": ("orchestrator", "172.16.14.201", "realman"),
    "W1": ("4090", "172.16.11.194", "user"),
    "W2": ("mac_min_8T", "172.16.12.50", "edge_sale"),
    "W3": ("gateway", "172.16.14.215", "realman"),
    "W4": ("data_center", "172.16.14.90", "realman"),
}

# ── 测试类型 ──

TEST_TYPES = {
    "http":         "HTTP 端点检查",
    "db":           "数据库验证",
    "ssh_command":  "远程 Shell 命令",
    "git":          "Git 操作验证",
    "file_exists":  "文件存在性检查",
    "service":      "服务运行状态",
    "manual":       "需人工验证",
}


@dataclass
class AcceptanceCriterion:
    """从任务卡解析出的单个验收标准"""
    machine: str          # W0-W4
    task: str             # 任务名
    criterion: str        # 完成标志原文
    output_files: str     # 产出文件列
    day: str              # Day N
    sprint: str           # 如 "1-2"
    test_type: str = ""   # auto-classified

    def __post_init__(self):
        if not self.test_type:
            self.test_type = self._classify()

    def _classify(self) -> str:
        """根据完成标志文本自动分类测试类型"""
        c = self.criterion.lower()

        # HTTP 类
        if any(kw in c for kw in [
            "curl", "http", "/health", "返回 200", "返回200",
            "/v1/", "/api/", "swagger", "/docs",
        ]):
            return "http"

        # 数据库类
        if any(kw in c for kw in ["psql", "redis-cli", "select", "数据库", "种子数据"]):
            return "db"

        # Nginx / 系统命令类
        if any(kw in c for kw in ["nginx -t", "systemctl", "cron", "crontab"]):
            return "ssh_command"

        # Git 类
        if any(kw in c for kw in ["git push", "git pull", "git仓库", "互通"]):
            return "git"

        # 文件存在类
        if any(ext in c for ext in [".py", ".yaml", ".sql", ".sh", ".conf", ".json"]):
            return "file_exists"

        # 服务运行类
        if any(kw in c for kw in ["启动", "运行", "端到端", "链路", "稳定"]):
            return "service"

        return "manual"

    def to_dict(self) -> Dict:
        return {
            "machine": self.machine,
            "task": self.task,
            "criterion": self.criterion,
            "day": self.day,
            "sprint": self.sprint,
            "test_type": self.test_type,
        }


class AcceptanceGenerator:
    """
    从任务卡 Markdown 解析验收标准，生成测试代码骨架。
    """

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.task_card_path = self.repo_root / "docs" / "07-Sprint任务卡.md"

    def parse_criteria(self, sprint: Optional[str] = None) -> List[AcceptanceCriterion]:
        """
        解析任务卡中的验收标准。

        :param sprint: 如 "1-2", "3-4"。None 表示全部。
        :return: 验收标准列表
        """
        if not self.task_card_path.exists():
            log.error("任务卡文件不存在: %s", self.task_card_path)
            return []

        content = self.task_card_path.read_text(encoding="utf-8")

        if sprint:
            content = self._extract_sprint_section(content, sprint)
            if not content:
                log.warning("未找到 Sprint %s 的章节", sprint)
                return []

        return self._parse_tables(content, sprint or "all")

    def _extract_sprint_section(self, content: str, sprint: str) -> str:
        """提取指定 Sprint 的 Markdown 章节"""
        # Sprint 标题格式: ## N. Sprint X-Y：...
        pattern = rf"##\s+\d+\.\s+Sprint\s+{re.escape(sprint)}"
        match = re.search(pattern, content)
        if not match:
            return ""

        # 到下一个同级标题为止
        rest = content[match.start():]
        next_h2 = re.search(r"\n##\s+\d+\.\s+Sprint\s+", rest[10:])
        if next_h2:
            return rest[:10 + next_h2.start()]
        return rest

    def _parse_tables(self, section: str, sprint: str) -> List[AcceptanceCriterion]:
        """从 Markdown 章节中解析表格行"""
        criteria = []
        current_day = "?"

        # Day 标题
        day_re = re.compile(r"####?\s+Day\s+(\d+)")

        # 表格行: | **W1** | 任务 | 指令 | 产出 | 完成标志 |
        # 也支持非粗体: | W1 | ... |
        row_re = re.compile(
            r"\|\s*\*{0,2}(W\d+)\*{0,2}\s*\|"       # 机器 (W0-W4)
            r"\s*([^|]+?)\s*\|"                        # 任务
            r"\s*([^|]*?)\s*\|"                        # aider 指令
            r"\s*([^|]*?)\s*\|"                        # 产出文件
            r"\s*([^|]+?)\s*\|"                        # 完成标志
        )

        # 合并行 (跨多机器, 如 "W1-W4")
        merged_re = re.compile(
            r"\|\s*\*{0,2}(W\d+[-–]W\d+)\*{0,2}\s*\|"
            r"\s*([^|]+?)\s*\|"
            r"\s*([^|]*?)\s*\|"
            r"\s*([^|]*?)\s*\|"
            r"\s*([^|]+?)\s*\|"
        )

        for line in section.splitlines():
            # Day 标题
            day_m = day_re.search(line)
            if day_m:
                current_day = day_m.group(1)
                continue

            # 表头行 / 分隔行
            if "---" in line or "机器" in line or "完成标志" in line:
                continue

            # 单机行
            row_m = row_re.search(line)
            if row_m:
                machine = row_m.group(1).strip()
                task = row_m.group(2).strip()
                output_files = row_m.group(4).strip()
                criterion = row_m.group(5).strip()

                if criterion and criterion != "—":
                    criteria.append(AcceptanceCriterion(
                        machine=machine,
                        task=task,
                        criterion=criterion,
                        output_files=output_files,
                        day=current_day,
                        sprint=sprint,
                    ))
                continue

            # 合并行 (W1-W4)
            merged_m = merged_re.search(line)
            if merged_m:
                machines_range = merged_m.group(1).strip()
                task = merged_m.group(2).strip()
                output_files = merged_m.group(4).strip()
                criterion = merged_m.group(5).strip()

                if criterion and criterion != "—":
                    criteria.append(AcceptanceCriterion(
                        machine=machines_range,
                        task=task,
                        criterion=criterion,
                        output_files=output_files,
                        day=current_day,
                        sprint=sprint,
                    ))

        return criteria

    # ── 报告生成 ──

    def generate_report(self, sprint: Optional[str] = None) -> str:
        """生成验收标准分析报告 (Markdown)"""
        criteria = self.parse_criteria(sprint)
        sprint_label = sprint or "全部"

        if not criteria:
            return f"Sprint {sprint_label}: 未解析到验收标准"

        lines = [
            f"# Sprint {sprint_label} 验收标准分析",
            f"共 **{len(criteria)}** 个验收点\n",
            "## 验收点列表",
            "",
            "| Day | 机器 | 类型 | 任务 | 完成标志 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for c in criteria:
            type_label = TEST_TYPES.get(c.test_type, c.test_type)
            lines.append(
                f"| {c.day} | {c.machine} | {type_label} | {c.task[:20]} | {c.criterion[:40]} |"
            )

        # 统计
        type_counts: Dict[str, int] = {}
        for c in criteria:
            type_counts[c.test_type] = type_counts.get(c.test_type, 0) + 1

        machine_counts: Dict[str, int] = {}
        for c in criteria:
            machine_counts[c.machine] = machine_counts.get(c.machine, 0) + 1

        lines.append("\n## 测试类型分布\n")
        for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            label = TEST_TYPES.get(t, t)
            lines.append(f"- **{label}** ({t}): {count}")

        lines.append("\n## 机器分布\n")
        for m, count in sorted(machine_counts.items()):
            name = MACHINE_MAP.get(m, (m,))[0] if m in MACHINE_MAP else m
            lines.append(f"- **{m}** ({name}): {count}")

        # 可自动化比率
        auto = sum(1 for c in criteria if c.test_type != "manual")
        lines.append(f"\n## 自动化覆盖\n")
        lines.append(f"- 可自动化: {auto}/{len(criteria)} ({100*auto//len(criteria)}%)")
        lines.append(f"- 需人工:   {len(criteria)-auto}/{len(criteria)}")

        return "\n".join(lines)

    # ── 测试骨架生成 ──

    def generate_test_skeleton(self, sprint: str) -> str:
        """从验收标准生成 pytest 测试骨架代码"""
        criteria = self.parse_criteria(sprint)
        if not criteria:
            return f"# Sprint {sprint}: 无验收标准\n"

        sprint_safe = sprint.replace("-", "_")

        lines = [
            '"""',
            f'Sprint {sprint} 验收测试 (自动生成)',
            f'共 {len(criteria)} 个验收点',
            f'运行: RUN_ACCEPTANCE=1 python3 -m pytest tests/acceptance/test_sprint_{sprint_safe}.py -v',
            '"""',
            'from __future__ import annotations',
            '',
            'import pytest',
            'from .conftest import ssh_check, http_get, http_post, SERVICE_ENDPOINTS, MACHINE_HOSTS',
            '',
        ]

        # 按 Day 分组
        by_day: Dict[str, List[AcceptanceCriterion]] = {}
        for c in criteria:
            by_day.setdefault(c.day, []).append(c)

        for day, items in sorted(by_day.items(), key=lambda x: x[0]):
            class_name = f"TestDay{day}"
            lines.append(f"\nclass {class_name}:")
            lines.append(f'    """Day {day} 验收"""')

            for i, c in enumerate(items):
                func_name = f"test_{c.machine.lower()}_day{day}_{i+1}"
                lines.append(f"")
                lines.append(f"    def {func_name}(self):")
                lines.append(f'        """{c.machine}: {c.criterion[:60]}"""')

                if c.test_type == "http":
                    lines.append(f"        # HTTP 检查: {c.criterion}")
                    lines.append(f"        # TODO: 解析 URL/端口，补充具体断言")
                    lines.append(f"        pass")
                elif c.test_type == "db":
                    lines.append(f"        # DB 检查: {c.criterion}")
                    lines.append(f'        result = ssh_check("{c.machine}", \'psql -U ai_crm -d ai_crm -c "SELECT 1"\')')
                    lines.append(f"        assert result.returncode == 0")
                elif c.test_type == "ssh_command":
                    lines.append(f"        # SSH 命令: {c.criterion}")
                    lines.append(f'        result = ssh_check("{c.machine}", "echo test")')
                    lines.append(f"        assert result.returncode == 0")
                elif c.test_type == "git":
                    lines.append(f"        # Git 检查: {c.criterion}")
                    lines.append(f'        result = ssh_check("{c.machine}", "cd ~/ai-crm && git status")')
                    lines.append(f"        assert result.returncode == 0")
                else:
                    lines.append(f"        # {c.test_type}: {c.criterion}")
                    lines.append(f"        pytest.skip('需人工验证: {c.criterion[:40]}')")

        return "\n".join(lines) + "\n"


# ── CLI ──

def main():
    parser = argparse.ArgumentParser(
        description="从任务卡 '完成标志' 列解析验收标准",
    )
    parser.add_argument(
        "--sprint", default=None,
        help="Sprint 编号, 如 1-2, 3-4。不指定则分析全部",
    )
    parser.add_argument(
        "--repo", default=".",
        help="仓库根目录 (默认当前目录)",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="输出 Markdown 分析报告",
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="生成测试骨架代码到 stdout",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    gen = AcceptanceGenerator(args.repo)

    if args.report:
        print(gen.generate_report(args.sprint))
    elif args.generate:
        sprint = args.sprint or "1-2"
        print(gen.generate_test_skeleton(sprint))
    else:
        # 默认: 列出验收标准
        criteria = gen.parse_criteria(args.sprint)
        sprint_label = args.sprint or "全部"
        print(f"Sprint {sprint_label}: 解析到 {len(criteria)} 个验收标准\n")
        for c in criteria:
            type_label = TEST_TYPES.get(c.test_type, c.test_type)
            print(f"  Day{c.day:>2s} | {c.machine:<5s} | {type_label:<12s} | {c.criterion}")


if __name__ == "__main__":
    main()
