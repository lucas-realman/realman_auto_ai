"""
Sirus AI-CRM DingTalk Bot Server
钉钉机器人 webhook 服务端

接收钉钉消息回调，解析意图，调用 CRM API，返回交互卡片。
"""

import hashlib
import hmac
import base64
import json
import logging
import time
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from config import settings
from message_parser import parse_intent, Intent
from card_templates import (
    lead_list_card,
    customer_detail_card,
    opportunity_card,
    help_card,
    error_card,
    success_card,
)
from dingtalk_client import DingTalkClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Sirus CRM DingTalk Bot", version="0.1.0")
dt_client = DingTalkClient()

CRM_BASE = settings.crm_api_base.rstrip("/")


# ---------- helpers ----------

def verify_signature(timestamp: str, sign: str) -> bool:
    """验证钉钉回调签名"""
    if not settings.dingtalk_app_secret:
        return True  # 开发模式跳过验签
    string_to_sign = f"{timestamp}\n{settings.dingtalk_app_secret}"
    hmac_code = hmac.new(
        settings.dingtalk_app_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected = base64.b64encode(hmac_code).decode("utf-8")
    return sign == expected


async def crm_get(path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """GET 请求 CRM API"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{CRM_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


async def crm_post(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """POST 请求 CRM API"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{CRM_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


async def crm_put(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """PUT 请求 CRM API"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.put(f"{CRM_BASE}{path}", json=data)
        resp.raise_for_status()
        return resp.json()


# ---------- intent handlers ----------

async def handle_list_leads(params: Dict) -> Dict:
    """处理列出线索请求"""
    try:
        result = await crm_get("/api/v1/leads", params={"page": 1, "size": 10})
        return lead_list_card(result.get("items", []), result.get("total", 0))
    except Exception as e:
        logger.error(f"获取线索列表失败: {e}")
        return error_card(f"获取线索列表失败: {e}")


async def handle_search_customer(params: Dict) -> Dict:
    """处理搜索客户请求"""
    try:
        keyword = params.get("keyword", "")
        result = await crm_get("/api/v1/customers", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if keyword:
            items = [c for c in items if keyword.lower() in (c.get("companyName", "") or "").lower()]
        if items:
            return customer_detail_card(items[0])
        return error_card(f"未找到匹配「{keyword}」的客户")
    except Exception as e:
        logger.error(f"搜索客户失败: {e}")
        return error_card(f"搜索客户失败: {e}")


async def handle_create_lead(params: Dict) -> Dict:
    """处理创建线索请求"""
    try:
        data = {
            "companyName": params.get("company", "未命名公司"),
            "contactName": params.get("contact", "未知联系人"),
            "phone": params.get("phone"),
            "source": params.get("source", "dingtalk"),
        }
        result = await crm_post("/api/v1/leads", data)
        return success_card(f"线索创建成功！\n公司: {result.get('companyName')}\nID: {result.get('id')}")
    except Exception as e:
        logger.error(f"创建线索失败: {e}")
        return error_card(f"创建线索失败: {e}")


async def handle_opportunity_info(params: Dict) -> Dict:
    """处理查看商机请求"""
    try:
        result = await crm_get("/api/v1/opportunities", params={"page": 1, "size": 5})
        items = result.get("items", [])
        if items:
            return opportunity_card(items[0])
        return error_card("暂无商机数据")
    except Exception as e:
        logger.error(f"获取商机失败: {e}")
        return error_card(f"获取商机失败: {e}")


async def handle_convert_lead(params: Dict) -> Dict:
    """处理转化线索请求"""
    try:
        lead_id = params.get("lead_id")
        if not lead_id:
            return error_card("请提供线索ID，如: 转化线索 abc123")
        result = await crm_post(f"/api/v1/leads/{lead_id}/convert", {})
        return success_card(f"线索已转化为客户！\n公司: {result.get('companyName', '未知')}")
    except Exception as e:
        logger.error(f"转化线索失败: {e}")
        return error_card(f"转化线索失败: {e}")


INTENT_HANDLERS = {
    Intent.LIST_LEADS: handle_list_leads,
    Intent.SEARCH_CUSTOMER: handle_search_customer,
    Intent.CREATE_LEAD: handle_create_lead,
    Intent.OPPORTUNITY_INFO: handle_opportunity_info,
    Intent.CONVERT_LEAD: handle_convert_lead,
}


# ---------- routes ----------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "dingtalk-bot"}


@app.post("/webhook/dingtalk")
async def dingtalk_webhook(request: Request):
    """
    钉钉机器人消息回调入口
    
    接收格式:
    {
        "msgtype": "text",
        "text": {"content": "查看线索"},
        "senderNick": "张三",
        "senderId": "xxx",
        "conversationId": "cid...",
        "conversationType": "1" | "2",
        ...
    }
    """
    body = await request.json()
    logger.info(f"收到钉钉消息: {json.dumps(body, ensure_ascii=False)[:500]}")

    # 签名验证 (如果配置了 app_secret)
    timestamp = request.headers.get("timestamp", "")
    sign = request.headers.get("sign", "")
    if settings.dingtalk_app_secret and not verify_signature(timestamp, sign):
        logger.warning("签名验证失败")
        raise HTTPException(status_code=403, detail="签名验证失败")

    # 解析消息文本
    msg_type = body.get("msgtype", "text")
    if msg_type == "text":
        content = body.get("text", {}).get("content", "").strip()
    else:
        content = ""

    sender_nick = body.get("senderNick", "用户")
    conversation_type = body.get("conversationType", "1")
    webhook_url = body.get("sessionWebhook", "")

    if not content:
        card = help_card()
    else:
        # 解析意图
        intent, params = parse_intent(content)
        logger.info(f"意图: {intent}, 参数: {params}")

        handler = INTENT_HANDLERS.get(intent)
        if handler:
            card = await handler(params)
        else:
            card = help_card()

    # 回复消息
    if webhook_url:
        # 使用 session webhook 回复
        try:
            await dt_client.send_card(webhook_url, card)
        except Exception as e:
            logger.error(f"发送卡片失败: {e}")
            # fallback: 发送纯文本
            await dt_client.send_text(webhook_url, "处理请求时出错，请稍后再试。")
    
    return {"msgtype": "empty"}


@app.post("/webhook/dingtalk/interactive")
async def dingtalk_interactive(request: Request):
    """
    钉钉交互卡片回调
    处理卡片上的按钮点击事件
    """
    body = await request.json()
    logger.info(f"收到交互回调: {json.dumps(body, ensure_ascii=False)[:500]}")

    action_value = body.get("value", {})
    action = action_value.get("action", "")

    result_card = {}
    if action == "convert_lead":
        lead_id = action_value.get("lead_id", "")
        result_card = await handle_convert_lead({"lead_id": lead_id})
    elif action == "view_detail":
        entity_type = action_value.get("type", "")
        entity_id = action_value.get("id", "")
        if entity_type == "customer":
            try:
                detail = await crm_get(f"/api/v1/customers/{entity_id}")
                result_card = customer_detail_card(detail)
            except Exception as e:
                result_card = error_card(str(e))
    elif action == "advance_stage":
        opp_id = action_value.get("opp_id", "")
        next_stage = action_value.get("next_stage", "")
        if opp_id and next_stage:
            result_card = await handle_advance_opportunity(opp_id, next_stage)
        else:
            result_card = error_card("缺少参数")
    else:
        result_card = help_card()

    return result_card


async def handle_advance_opportunity(opp_id: str, next_stage: str) -> Dict:
    """推进商机阶段"""
    try:
        result = await crm_put(f"/api/v1/opportunities/{opp_id}", {"stage": next_stage})
        return success_card(f"商机阶段已推进到: {next_stage}\n商机: {result.get('name', '')}")
    except Exception as e:
        logger.error(f"推进商机阶段失败: {e}")
        return error_card(f"推进商机阶段失败: {e}")


# ---------- startup ----------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bot_server:app",
        host="0.0.0.0",
        port=settings.bot_port,
        reload=True,
    )
