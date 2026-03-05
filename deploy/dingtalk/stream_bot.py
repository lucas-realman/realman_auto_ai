"""
Sirus AI-CRM 钉钉 Stream 机器人
================================
通过钉钉 Stream 长连接 (WebSocket) 接收消息，无需公网 IP。

用法:
    python stream_bot.py

前置条件:
    pip install dingtalk-stream

钉钉开发者后台配置:
    1. 打开 https://open-dev.dingtalk.com/
    2. 进入应用 → 机器人与消息推送 → 启用
    3. 消息接收模式选择 "Stream 模式"
    4. 保存即可，不需要填回调地址
"""

import asyncio
import json
import logging
import sys
import signal
from typing import Dict, Any

import httpx
import dingtalk_stream
from dingtalk_stream import AckMessage

from config import settings
from message_parser import parse_intent, Intent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("stream_bot")

CRM_BASE = settings.crm_api_base.rstrip("/")

# ────────────────────── CRM helpers ──────────────────────

def _http_client():
    return httpx.Client(timeout=10, follow_redirects=True)


def crm_get(path: str, params=None) -> Dict[str, Any]:
    with _http_client() as c:
        resp = c.get(f"{CRM_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


def crm_post(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    with _http_client() as c:
        resp = c.post(f"{CRM_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


# ────────────────────── Intent handlers (sync) ──────────────────────

def handle_list_leads(params: Dict) -> str:
    try:
        result = crm_get("/api/v1/leads", params={"page": 1, "size": 10})
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            return "📭 暂无线索数据"
        lines = [f"📋 线索列表 (共 {total} 条)\n"]
        for i, lead in enumerate(items, 1):
            lines.append(
                f"{i}. {lead.get('companyName', '未知')} — "
                f"{lead.get('contactName', '')} "
                f"{lead.get('phone', '')} "
                f"[{lead.get('status', '')}]"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 获取线索失败: {e}"


def handle_search_customer(params: Dict) -> str:
    try:
        keyword = params.get("keyword", "")
        result = crm_get("/api/v1/customers", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if keyword:
            items = [c for c in items if keyword.lower() in (c.get("companyName", "") or "").lower()]
        if not items:
            return f"🔍 未找到匹配「{keyword}」的客户"
        c = items[0]
        return (
            f"👤 客户详情\n"
            f"  公司: {c.get('companyName', '')}\n"
            f"  联系人: {c.get('contactPerson', '')}\n"
            f"  行业: {c.get('industry', '未知')}\n"
            f"  级别: {c.get('level', '未知')}\n"
            f"  ID: {c.get('id', '')}"
        )
    except Exception as e:
        return f"❌ 搜索客户失败: {e}"


def handle_create_lead(params: Dict) -> str:
    try:
        data = {
            "companyName": params.get("company_name", params.get("company", "未命名公司")),
            "contactName": params.get("contact_name", params.get("contact", "未知联系人")),
            "phone": params.get("phone"),
            "source": "dingtalk",
        }
        result = crm_post("/api/v1/leads", data)
        return (
            f"✅ 线索创建成功！\n"
            f"  公司: {result.get('companyName')}\n"
            f"  联系人: {result.get('contactName')}\n"
            f"  ID: {result.get('id')}"
        )
    except Exception as e:
        return f"❌ 创建线索失败: {e}"


def handle_opportunity_info(params: Dict) -> str:
    try:
        result = crm_get("/api/v1/opportunities", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if not items:
            return "📭 暂无商机数据"
        total = result.get("total", 0)
        lines = [f"💼 商机列表 (共 {total} 条)\n"]
        for i, opp in enumerate(items, 1):
            lines.append(
                f"{i}. {opp.get('name', '未命名')} — "
                f"阶段: {opp.get('stage', '')} "
                f"金额: ¥{opp.get('amount', 0):,.0f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ 获取商机失败: {e}"


def handle_help(params: Dict) -> str:
    return (
        "🤖 Sirus AI-CRM 机器人指令帮助\n\n"
        "指令          | 示例                          | 说明\n"
        "------------- | ----------------------------- | ----\n"
        "查线索        | 查线索 Test                    | 搜索线索列表\n"
        "新建线索      | 新建线索 公司名 联系人 手机号   | 创建新线索\n"
        "客户详情      | 客户详情 XX公司                | 查看客户信息\n"
        "推进商机      | 推进商机 XX                    | 查看商机信息\n"
        "最近活动      | 最近活动                       | 查看最近活动\n"
        "帮助          | 帮助                           | 显示本帮助"
    )


INTENT_HANDLERS = {
    Intent.LIST_LEADS: handle_list_leads,
    Intent.SEARCH_CUSTOMER: handle_search_customer,
    Intent.CREATE_LEAD: handle_create_lead,
    Intent.OPPORTUNITY_INFO: handle_opportunity_info,
    Intent.HELP: handle_help,
}


def process_message(text: str) -> str:
    """解析意图并调用对应 handler，返回纯文本回复"""
    text = text.strip()
    if not text:
        return handle_help({})

    intent, params = parse_intent(text)
    logger.info(f"消息: {text} → 意图: {intent}, 参数: {params}")

    handler = INTENT_HANDLERS.get(intent)
    if handler:
        return handler(params)
    return f"🤔 不太理解: 「{text}」\n\n发送 帮助 查看可用指令"


# ────────────────────── DingTalk Stream Handler ──────────────────────

class CRMBotHandler(dingtalk_stream.ChatbotHandler):
    """处理钉钉 Stream 下发的机器人消息"""

    def process(self, callback: dingtalk_stream.CallbackMessage) -> AckMessage:
        """
        callback.data 可能是 dict 或 JSON 字符串，格式:
        {
            "conversationId": "...",
            "senderNick": "张三",
            "conversationType": "1",   // 1=单聊 2=群聊
            "msgtype": "text",
            "text": {"content": "查线索"},
            "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=..."
        }
        """
        try:
            incoming = callback.data
            if isinstance(incoming, str):
                incoming = json.loads(incoming)
            logger.info(
                f"收到钉钉消息: senderNick={incoming.get('senderNick')}, "
                f"type={incoming.get('conversationType')}"
            )

            # 提取文本
            msg_type = incoming.get("msgtype", "text")
            if msg_type == "text":
                content = incoming.get("text", {}).get("content", "").strip()
            else:
                content = ""

            # 处理消息
            reply_text = process_message(content)

            # 通过 sessionWebhook 回复
            webhook_url = incoming.get("sessionWebhook", "")
            if webhook_url:
                self._reply_text(webhook_url, reply_text)
            else:
                logger.warning("没有 sessionWebhook，无法回复")

        except Exception as e:
            logger.error(f"处理消息异常: {e}", exc_info=True)

        return AckMessage.STATUS_OK, "OK"

    async def async_process(self, callback: dingtalk_stream.CallbackMessage):
        """异步版本 process，dingtalk-stream >= 0.20 会优先调用此方法"""
        return self.process(callback)

    def _reply_text(self, webhook_url: str, text: str):
        """通过 sessionWebhook 发送纯文本回复"""
        payload = {
            "msgtype": "text",
            "text": {"content": text},
        }
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("errcode", 0) != 0:
                        logger.error(f"钉钉回复失败: {result}")
                    else:
                        logger.info("回复成功 ✓")
                else:
                    logger.error(f"钉钉回复 HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"发送回复异常: {e}")


# ────────────────────── Main ──────────────────────

def main():
    app_key = settings.dingtalk_app_key
    app_secret = settings.dingtalk_app_secret

    if not app_key or not app_secret:
        logger.error("❌ 缺少 DINGTALK_APP_KEY / DINGTALK_APP_SECRET，请检查 config.py 或 .env")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("🚀 Sirus AI-CRM DingTalk Stream Bot")
    logger.info(f"   AppKey:   {app_key[:8]}...")
    logger.info(f"   CRM API:  {CRM_BASE}")
    logger.info("=" * 50)

    # 验证 CRM API 可达
    try:
        with httpx.Client(timeout=5, follow_redirects=True) as c:
            resp = c.get(f"{CRM_BASE}/health")
            logger.info(f"   CRM 健康检查: {resp.json()}")
    except Exception as e:
        logger.warning(f"   ⚠ CRM API 不可达: {e}（Bot 仍将启动，但 CRM 调用会失败）")

    # 构建 Stream 客户端
    credential = dingtalk_stream.Credential(app_key, app_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)

    # 注册机器人消息回调
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC,
        CRMBotHandler(),
    )

    logger.info("🔗 正在连接钉钉 Stream 服务...")
    logger.info("   (内网无需公网 IP，Bot 主动建立 WebSocket 出站连接)")
    logger.info("   按 Ctrl+C 停止")

    # 启动（阻塞）
    client.start_forever()


if __name__ == "__main__":
    main()
