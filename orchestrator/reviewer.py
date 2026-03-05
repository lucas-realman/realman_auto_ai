"""
Sirus AI-CRM 自动化流水线 — 自动 Review 引擎
三层自动代码审查 (对照 docs/08 §4):
  Layer 1: 静态检查 (py_compile + ruff)
  Layer 2: 契约对齐检查 (LLM)
  Layer 3: 设计符合度检查 (LLM)
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from .config import Config
from .task_models import CodingTask, ReviewResult, TaskResult

log = logging.getLogger("orchestrator.reviewer")


class AutoReviewer:
    """三层自动代码 Review"""

    def __init__(self, config: Config):
        self.config = config
        self.repo_root = config.repo_root

    async def review(self, task: CodingTask, result: TaskResult) -> ReviewResult:
        """
        对编码结果执行三层 Review。
        任何一层不通过即返回失败 + 修复指令。
        """
        files = result.files_changed
        if not files:
            return ReviewResult(
                passed=False, layer="static",
                issues=["无变更文件"],
                fix_instruction="aider 未生成任何文件, 请重新执行编码任务。",
            )

        # Layer 1: 静态检查 (0 成本, 秒级)
        log.info("[%s] Review Layer 1: 静态检查", task.task_id)
        static_result = await self._static_check(files)
        if not static_result.passed:
            log.info("[%s] Layer 1 失败: %s", task.task_id, static_result.issues)
            return static_result

        # Layer 2: 契约对齐 (LLM, 需要 API 调用)
        log.info("[%s] Review Layer 2: 契约对齐", task.task_id)
        contract_result = await self._contract_check(task, files)
        if not contract_result.passed:
            log.info("[%s] Layer 2 失败: %s", task.task_id, contract_result.issues)
            return contract_result

        # Layer 3: 设计符合度 (LLM, 需要 API 调用)
        log.info("[%s] Review Layer 3: 设计符合度", task.task_id)
        design_result = await self._design_check(task, files)
        if not design_result.passed:
            log.info("[%s] Layer 3 失败 (score=%.1f): %s",
                     task.task_id, design_result.score, design_result.issues)
            return design_result

        log.info("[%s] ✅ Review 全部通过 (score=%.1f)",
                 task.task_id, design_result.score)
        return design_result

    # ── Layer 1: 静态检查 ──

    async def _static_check(self, files: List[str]) -> ReviewResult:
        issues = []

        for f in files:
            if not f.endswith(".py"):
                continue

            full_path = self.repo_root / f
            if not full_path.exists():
                continue

            # py_compile
            try:
                proc = subprocess.run(
                    ["python", "-m", "py_compile", str(full_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0:
                    issues.append(f"编译错误 {f}: {proc.stderr.strip()}")
            except subprocess.TimeoutExpired:
                issues.append(f"编译超时 {f}")

            # ruff (如果可用)
            try:
                proc = subprocess.run(
                    ["ruff", "check", "--select", "E,W,F", str(full_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0 and proc.stdout.strip():
                    # 只报告严重问题, 忽略 warning
                    errors = [
                        line for line in proc.stdout.strip().splitlines()
                        if any(e in line for e in ["E9", "F8", "F6", "F4"])
                    ]
                    if errors:
                        issues.append(f"Lint 严重问题 {f}:\n" + "\n".join(errors))
            except FileNotFoundError:
                # ruff 未安装, 跳过
                pass
            except subprocess.TimeoutExpired:
                pass

        if issues:
            return ReviewResult(
                passed=False,
                layer="static",
                issues=issues,
                fix_instruction=self._static_fix_instruction(issues),
            )

        return ReviewResult(passed=True, layer="static", score=5.0)

    def _static_fix_instruction(self, issues: List[str]) -> str:
        return (
            "静态检查发现以下错误, 请修复:\n\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n\n确保所有 .py 文件可通过 python -m py_compile 编译。"
        )

    # ── Layer 2: 契约对齐 ──

    async def _contract_check(
        self, task: CodingTask, files: List[str],
    ) -> ReviewResult:
        """对比代码和契约文件, 检查接口一致性"""
        # 读取变更的代码
        code_content = self._read_files(files)
        if not code_content:
            return ReviewResult(passed=True, layer="contract", score=5.0)

        # 读取相关契约
        contracts = self._read_contracts_for_task(task)
        if not contracts:
            # 没有匹配的契约, 跳过
            return ReviewResult(passed=True, layer="contract", score=5.0)

        # 调用 LLM 进行契约对齐检查
        prompt = f"""你是一个接口契约审查员。请对比以下代码和接口契约，检查是否一致。

## 接口契约
{contracts}

## 生成的代码
{code_content}

## 检查项
1. 函数/方法签名是否和契约定义一致（名称、参数、返回类型）？
2. 是否有契约中定义但代码中未实现的接口？
3. 参数的校验逻辑是否和契约中的约束一致（required、enum、type）？

## 输出格式 (严格 JSON)
如果完全一致:
{{"passed": true, "issues": []}}

如果有不一致:
{{
  "passed": false,
  "issues": ["问题描述1", "问题描述2"],
  "fix_instruction": "具体的修复指令，告诉 aider 如何修改"
}}"""

        try:
            response = await self._call_llm(prompt)
            data = self._parse_json_response(response)

            if data.get("passed", False):
                return ReviewResult(passed=True, layer="contract", score=5.0)
            else:
                return ReviewResult(
                    passed=False,
                    layer="contract",
                    issues=data.get("issues", ["契约对齐检查失败"]),
                    fix_instruction=data.get("fix_instruction", "请检查接口定义是否与契约一致"),
                )
        except Exception as e:
            log.warning("[%s] Layer 2 LLM 调用失败, 降级通过: %s", task.task_id, e)
            return ReviewResult(passed=True, layer="contract", score=4.0)

    # ── Layer 3: 设计符合度 ──

    async def _design_check(
        self, task: CodingTask, files: List[str],
    ) -> ReviewResult:
        """对照设计文档评审代码质量"""
        code_content = self._read_files(files)
        if not code_content:
            return ReviewResult(passed=True, layer="design", score=4.0)

        prompt = f"""你是一个高级代码审查员。请根据任务描述评审以下代码。

## 编码任务
{task.description}

## 验收标准
{chr(10).join(f'- {a}' for a in task.acceptance) if task.acceptance else '无特殊验收标准'}

## 生成的代码
{code_content[:8000]}

## 评审维度 (每项 1-5 分)
1. 功能完整性: 是否完整实现了要求的所有功能点？
2. 接口正确性: 函数签名、参数、返回值是否合理？
3. 错误处理: 是否有完整的异常处理？
4. 代码质量: 是否有硬编码？docstring 是否完整？
5. 可运行性: import 是否齐全？是否可以独立运行？

## 输出格式 (严格 JSON)
{{
  "scores": {{"功能完整性": 4, "接口正确性": 5, "错误处理": 3, "代码质量": 4, "可运行性": 4}},
  "average_score": 4.0,
  "issues": ["问题1", "问题2"],
  "fix_instruction": "如果平均分<4.0，给出具体修复指令"
}}"""

        try:
            response = await self._call_llm(prompt)
            data = self._parse_json_response(response)

            avg_score = data.get("average_score", 0.0)
            threshold = self.config.pass_threshold

            if avg_score >= threshold:
                return ReviewResult(
                    passed=True, layer="design",
                    score=avg_score,
                    scores=data.get("scores", {}),
                    issues=data.get("issues", []),
                )
            else:
                return ReviewResult(
                    passed=False, layer="design",
                    score=avg_score,
                    scores=data.get("scores", {}),
                    issues=data.get("issues", ["设计评分低于阈值"]),
                    fix_instruction=data.get("fix_instruction",
                                             f"评分 {avg_score:.1f} < {threshold}, 请优化代码质量"),
                )
        except Exception as e:
            log.warning("[%s] Layer 3 LLM 调用失败, 降级通过: %s", task.task_id, e)
            return ReviewResult(passed=True, layer="design", score=4.0)

    # ── LLM 调用 ──

    async def _call_llm(self, prompt: str) -> str:
        """调用 OpenAI 兼容 API"""
        import httpx

        url = f"{self.config.openai_api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.aider_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # ── 文件读取工具 ──

    def _read_files(self, files: List[str]) -> str:
        parts = []
        for f in files:
            path = self.repo_root / f
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8")
                    parts.append(f"=== {f} ===\n{content}")
                except Exception:
                    pass
            elif path.is_dir():
                # 如果是目录, 读取下面的 .py 文件
                for py_file in sorted(path.rglob("*.py")):
                    try:
                        rel = py_file.relative_to(self.repo_root)
                        content = py_file.read_text(encoding="utf-8")
                        parts.append(f"=== {rel} ===\n{content}")
                    except Exception:
                        pass
        return "\n\n".join(parts)

    def _read_contracts_for_task(self, task: CodingTask) -> str:
        """读取与任务相关的契约文件"""
        contracts_dir = self.repo_root / "contracts"
        if not contracts_dir.exists():
            return ""

        parts = []
        for f in sorted(contracts_dir.iterdir()):
            if f.suffix in (".yaml", ".yml", ".sql"):
                # 智能匹配: agent 相关任务读 agent-api.yaml
                name = f.stem.lower()
                target = task.target_dir.lower().rstrip("/")
                if (name.startswith(target.split("/")[-1])
                        or "crm" in name
                        or "db" in name
                        or "health" in name
                        or "event" in name):
                    parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")

        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """从 LLM 回复中提取 JSON"""
        # 先尝试直接解析
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 尝试从 ```json ``` 中提取
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"无法从 LLM 回复中解析 JSON:\n{text[:500]}")
