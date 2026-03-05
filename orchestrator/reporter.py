"""
Sirus AI-CRM 自动化流水线 — 报告与通知
支持两种通知方式:
1. 钉钉自定义 Webhook 机器人 (简单, 推荐)
2. 钉钉企业内部应用 OpenAPI (使用已有机器人发群消息)
对应 docs/08 §6 "可观测性与报告"。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import base64
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from .config import Config
from .task_models import CodingTask, ReviewResult, TaskStatus, TestResult

log = logging.getLogger("orchestrator.reporter")


class Reporter:
    """
    通知 & 报告器。支持:
    1. 钉钉 Webhook 消息 (Markdown + 加签 + @mention)
    2. 钉钉企业内部应用 OpenAPI 机器人发群消息
    3. 本地 Markdown 报告文件
    """

    def __init__(self, config: Config):
        self.config = config
        # Webhook 模式
        self.webhook_url = config.get("notification.dingtalk_webhook", "")
        self.webhook_secret = config.get("notification.dingtalk_webhook_secret", "")
        # 企业机器人 OpenAPI 模式
        self.app_key = config.get("notification.dingtalk_app_key", "")
        self.app_secret = config.get("notification.dingtalk_app_secret", "")
        self.robot_code = config.get("notification.dingtalk_robot_code", "")
        self.conversation_id = config.get("notification.dingtalk_conversation_id", "")
        # @mention
        self.at_mobiles: List[str] = config.get("notification.at_mobiles", []) or []
        self.at_all: bool = config.get("notification.at_all", False) or False

        self.reports_dir = config.repo_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._start_time = time.time()
        self._access_token: Optional[str] = None
        self._token_expires: float = 0

    # ── 钉钉通知 ──

    async def notify_sprint_start(
        self, sprint_id: str, tasks: List[CodingTask],
    ) -> None:
        """Sprint 开始通知"""
        lines = [
            f"## 🚀 Sprint {sprint_id} 开始",
            f"**任务数**: {len(tasks)}",
            "",
            "| 任务 | 目标 | 机器 |",
            "| --- | --- | --- |",
        ]
        for t in tasks:
            lines.append(f"| {t.task_id} | {t.description[:30]} | {t.target_machine} |")
        await self._send_dingtalk(f"Sprint {sprint_id} 开始", "\n".join(lines))

    async def notify_task_dispatched(self, task: CodingTask) -> None:
        """任务已分发通知"""
        text = (
            f"## 📤 任务分发: {task.task_id}\n"
            f"- **机器**: {task.target_machine}\n"
            f"- **目录**: {task.target_dir}\n"
            f"- **描述**: {task.description[:60]}\n"
        )
        await self._send_dingtalk(f"任务分发: {task.task_id}", text)

    async def notify_task_result(
        self,
        task: CodingTask,
        review: Optional[ReviewResult] = None,
        test: Optional[TestResult] = None,
    ) -> None:
        """任务完成结果通知"""
        icon = "✅" if task.status == TaskStatus.PASSED else "❌"
        lines = [
            f"## {icon} 任务结果: {task.task_id}",
            f"- **状态**: {task.status.value}",
            f"- **机器**: {task.target_machine}",
            f"- **重试**: 编码 {task.retry_count}, 审查 {task.review_retry}, 测试 {task.test_retry}",
        ]
        if review:
            layer_val = review.layer.value if hasattr(review.layer, "value") else review.layer
            lines.append(f"- **审查**: {'通过' if review.passed else '未通过'} (层级: {layer_val})")
            if review.score is not None:
                lines.append(f"- **评分**: {review.score:.1f}")
        if test:
            lines.append(
                f"- **测试**: {test.passed_count}/{test.total} 通过, "
                f"{test.failed_count} 失败, 耗时 {test.duration_sec:.1f}s"
            )
        await self._send_dingtalk(f"任务结果: {task.task_id}", "\n".join(lines))

    async def notify_sprint_done(
        self,
        sprint_id: str,
        tasks: List[CodingTask],
    ) -> None:
        """Sprint 完成通知"""
        passed = sum(1 for t in tasks if t.status == TaskStatus.PASSED)
        failed = sum(1 for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.ESCALATED))
        lines = [
            f"## 🏁 Sprint {sprint_id} 完成",
            f"- **通过**: {passed}/{len(tasks)}",
            f"- **失败/升级**: {failed}/{len(tasks)}",
            f"- **耗时**: {self._elapsed()}",
            "",
            "### 详细",
            "| 任务 | 状态 | 重试 |",
            "| --- | --- | --- |",
        ]
        for t in tasks:
            icon = "✅" if t.status == TaskStatus.PASSED else "❌"
            lines.append(f"| {t.task_id} | {icon} {t.status.value} | {t.retry_count} |")
        await self._send_dingtalk(f"Sprint {sprint_id} 完成", "\n".join(lines))

    async def notify_error(self, message: str) -> None:
        """异常/错误通知"""
        text = f"## ⚠️ 流水线异常\n{message}"
        await self._send_dingtalk("流水线异常", text)

    # ── 本地报告 ──

    def save_sprint_report(
        self,
        sprint_id: str,
        tasks: List[CodingTask],
        summary: Dict,
    ) -> str:
        """生成 Sprint 报告 Markdown 文件, 返回文件路径"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sprint_{sprint_id}_{ts}.md"
        filepath = self.reports_dir / filename

        lines = [
            f"# Sprint {sprint_id} 报告",
            f"生成时间: {datetime.now().isoformat()}",
            f"耗时: {self._elapsed()}",
            "",
            "## 总结",
            f"- 总任务数: {summary.get('total', len(tasks))}",
            f"- 通过: {summary.get('passed', 0)}",
            f"- 失败: {summary.get('failed', 0)}",
            f"- 升级: {summary.get('escalated', 0)}",
            "",
            "## 任务明细",
            "",
            "| 任务ID | 机器 | 状态 | 编码重试 | 审查重试 | 测试重试 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for t in tasks:
            lines.append(
                f"| {t.task_id} | {t.target_machine} | {t.status.value} "
                f"| {t.retry_count} | {t.review_retry} | {t.test_retry} |"
            )
        lines.append("")

        # 失败任务详情
        failed = [t for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.ESCALATED)]
        if failed:
            lines.append("## 失败/升级任务详情")
            for t in failed:
                lines.append(f"\n### {t.task_id}")
                lines.append(f"- 描述: {t.description}")
                if t.fix_instruction:
                    lines.append(f"- 最后修复指令: {t.fix_instruction}")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        log.info("Sprint 报告已保存: %s", filepath)
        return str(filepath)

    # ── 内部方法 ──

    async def _send_dingtalk(self, title: str, markdown_text: str) -> None:
        """
        发送钉钉通知。
        优先使用 Webhook, 其次使用企业机器人 OpenAPI。
        """
        # 添加 @mention 文本
        if self.at_mobiles:
            at_text = " ".join(f"@{m}" for m in self.at_mobiles)
            markdown_text += f"\n\n{at_text}"

        # 方式 1: Webhook
        if self.webhook_url:
            await self._send_via_webhook(title, markdown_text)
            return

        # 方式 2: 企业机器人 OpenAPI
        if self.app_key and self.conversation_id:
            await self._send_via_openapi(title, markdown_text)
            return

        log.debug("未配置钉钉通知 (无 Webhook 也无 OpenAPI), 跳过: %s", title)

    async def _send_via_webhook(self, title: str, markdown_text: str) -> None:
        """通过自定义 Webhook 机器人发送 Markdown 消息"""
        url = self.webhook_url

        # 加签模式: 在 URL 上附加 timestamp + sign
        if self.webhook_secret:
            timestamp = str(int(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{self.webhook_secret}"
            hmac_code = hmac.new(
                self.webhook_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown_text,
            },
            "at": {
                "atMobiles": self.at_mobiles,
                "isAtAll": self.at_all,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    log.warning("钉钉 Webhook 通知失败: HTTP %d", resp.status_code)
                else:
                    data = resp.json()
                    if data.get("errcode", 0) != 0:
                        log.warning("钉钉 Webhook 错误: %s", data.get("errmsg"))
                    else:
                        log.info("钉钉 Webhook 通知发送成功: %s", title)
        except Exception as e:
            log.warning("钉钉 Webhook 通知异常: %s", e)

    async def _send_via_openapi(self, title: str, markdown_text: str) -> None:
        """通过企业内部应用 OpenAPI 发送群消息"""
        token = await self._get_access_token()
        if not token:
            log.warning("无法获取钉钉 access_token, 跳过通知")
            return

        # 使用机器人发送群消息 API
        url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
        headers = {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }
        payload = {
            "msgParam": json.dumps({
                "title": title,
                "text": markdown_text,
            }),
            "msgKey": "sampleMarkdown",
            "openConversationId": self.conversation_id,
            "robotCode": self.robot_code or self.app_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    log.info("钉钉 OpenAPI 通知发送成功: %s", title)
                else:
                    log.warning(
                        "钉钉 OpenAPI 通知失败: HTTP %d, %s",
                        resp.status_code, resp.text,
                    )
        except Exception as e:
            log.warning("钉钉 OpenAPI 通知异常: %s", e)

    async def _get_access_token(self) -> Optional[str]:
        """获取企业应用的 access_token (缓存)"""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        if not self.app_key or not self.app_secret:
            return None

        url = (
            f"https://oapi.dingtalk.com/gettoken"
            f"?appkey={self.app_key}&appsecret={self.app_secret}"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("errcode") == 0:
                    self._access_token = data["access_token"]
                    self._token_expires = time.time() + data.get("expires_in", 7200) - 60
                    return self._access_token
                else:
                    log.warning("获取 access_token 失败: %s", data.get("errmsg"))
        except Exception as e:
            log.warning("获取 access_token 异常: %s", e)
        return None

    def _elapsed(self) -> str:
        """格式化已用时间"""
        dt = time.time() - self._start_time
        m, s = divmod(int(dt), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"
