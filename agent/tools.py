"""CRM Tool Calling functions — signatures match contracts/agent-tools.yaml."""

import json
from typing import Any

import httpx

from agent.config import settings

BASE = settings.CRM_BASE_URL


async def _request(method: str, path: str, **kwargs: Any) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, f"{BASE}{path}", **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204:
            return {"success": True}
        return resp.json()


# ── Lead tools ──

async def create_lead(
    company_name: str,
    contact_name: str,
    phone: str | None = None,
    email: str | None = None,
    source: str | None = None,
    industry: str | None = None,
    notes: str | None = None,
) -> dict:
    body = {"company_name": company_name, "contact_name": contact_name}
    for k in ("phone", "email", "source", "industry", "notes"):
        v = locals()[k]
        if v is not None:
            body[k] = v
    return await _request("POST", "/leads", json=body)


async def query_leads(
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 10,
) -> dict:
    params: dict[str, Any] = {"page": page, "size": size}
    if keyword:
        params["q"] = keyword
    if status:
        params["status"] = status
    return await _request("GET", "/leads", params=params)


async def update_lead(
    lead_id: str,
    status: str | None = None,
    contact_name: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
) -> dict:
    body: dict[str, Any] = {}
    for k in ("status", "contact_name", "phone", "notes"):
        v = locals()[k]
        if v is not None:
            body[k] = v
    return await _request("PUT", f"/leads/{lead_id}", json=body)


async def convert_lead_to_customer(lead_id: str) -> dict:
    return await _request("POST", f"/leads/{lead_id}/convert")


# ── Customer tools ──

async def create_customer(
    company_name: str,
    industry: str | None = None,
    region: str | None = None,
    level: str | None = None,
    notes: str | None = None,
) -> dict:
    body: dict[str, Any] = {"company_name": company_name}
    for k in ("industry", "region", "level", "notes"):
        v = locals()[k]
        if v is not None:
            body[k] = v
    return await _request("POST", "/customers", json=body)


async def query_customers(
    keyword: str | None = None,
    level: str | None = None,
    page: int = 1,
    size: int = 10,
) -> dict:
    params: dict[str, Any] = {"page": page, "size": size}
    if keyword:
        params["q"] = keyword
    if level:
        params["level"] = level
    return await _request("GET", "/customers", params=params)


async def get_customer_360(customer_id: str) -> dict:
    return await _request("GET", f"/customers/{customer_id}")


# ── Opportunity tools ──

async def create_opportunity(
    name: str,
    customer_id: str,
    amount: float | None = None,
    expected_close_date: str | None = None,
    product_type: str | None = None,
) -> dict:
    body: dict[str, Any] = {"name": name, "customer_id": customer_id}
    for k in ("amount", "expected_close_date", "product_type"):
        v = locals()[k]
        if v is not None:
            body[k] = v
    return await _request("POST", "/opportunities", json=body)


async def query_opportunities(
    keyword: str | None = None,
    customer_id: str | None = None,
    stage: str | None = None,
    page: int = 1,
) -> dict:
    params: dict[str, Any] = {"page": page}
    if keyword:
        params["q"] = keyword
    if customer_id:
        params["customer_id"] = customer_id
    if stage:
        params["stage"] = stage
    return await _request("GET", "/opportunities", params=params)


async def update_opportunity_stage(
    opportunity_id: str,
    new_stage: str,
    lost_reason: str | None = None,
) -> dict:
    body: dict[str, Any] = {"stage": new_stage}
    if lost_reason:
        body["lost_reason"] = lost_reason
    return await _request("PUT", f"/opportunities/{opportunity_id}", json=body)


# ── Activity tools ──

async def create_activity(
    type: str,
    subject: str,
    content: str | None = None,
    customer_id: str | None = None,
    opportunity_id: str | None = None,
) -> dict:
    body: dict[str, Any] = {"type": type, "subject": subject}
    for k in ("content", "customer_id", "opportunity_id"):
        v = locals()[k]
        if v is not None:
            body[k] = v
    return await _request("POST", "/activities", json=body)


async def query_activities(
    customer_id: str | None = None,
    opportunity_id: str | None = None,
    type: str | None = None,
    page: int = 1,
) -> dict:
    params: dict[str, Any] = {"page": page}
    if customer_id:
        params["customer_id"] = customer_id
    if opportunity_id:
        params["opportunity_id"] = opportunity_id
    if type:
        params["type"] = type
    return await _request("GET", "/activities", params=params)


# ── Tool registry for OpenAI function calling ──

TOOL_FUNCTIONS: dict[str, Any] = {
    "create_lead": create_lead,
    "query_leads": query_leads,
    "update_lead": update_lead,
    "convert_lead_to_customer": convert_lead_to_customer,
    "create_customer": create_customer,
    "query_customers": query_customers,
    "get_customer_360": get_customer_360,
    "create_opportunity": create_opportunity,
    "query_opportunities": query_opportunities,
    "update_opportunity_stage": update_opportunity_stage,
    "create_activity": create_activity,
    "query_activities": query_activities,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "创建销售线索。从用户对话中提取公司名、联系人、电话等信息后调用。",
            "parameters": {
                "type": "object",
                "required": ["company_name", "contact_name"],
                "properties": {
                    "company_name": {"type": "string", "description": "公司名称"},
                    "contact_name": {"type": "string", "description": "联系人姓名"},
                    "phone": {"type": "string", "description": "联系电话"},
                    "email": {"type": "string", "description": "邮箱"},
                    "source": {"type": "string", "enum": ["website", "exhibition", "referral", "cold_call", "dingtalk", "other"], "description": "线索来源"},
                    "industry": {"type": "string", "description": "所属行业"},
                    "notes": {"type": "string", "description": "备注"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_leads",
            "description": "搜索线索。支持按公司名、联系人、手机号模糊搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词（公司名/联系人/手机号）"},
                    "status": {"type": "string", "enum": ["new", "contacted", "qualified", "converted", "closed"]},
                    "page": {"type": "integer", "default": 1},
                    "size": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead",
            "description": "更新线索信息（状态、联系方式、备注等）。",
            "parameters": {
                "type": "object",
                "required": ["lead_id"],
                "properties": {
                    "lead_id": {"type": "string", "description": "线索ID"},
                    "status": {"type": "string", "enum": ["new", "contacted", "qualified", "converted", "closed"]},
                    "contact_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_lead_to_customer",
            "description": "将已确认的线索转化为正式客户，同时创建联系人。",
            "parameters": {
                "type": "object",
                "required": ["lead_id"],
                "properties": {
                    "lead_id": {"type": "string", "description": "要转化的线索ID"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_customer",
            "description": "直接创建客户（非线索转化场景）。",
            "parameters": {
                "type": "object",
                "required": ["company_name"],
                "properties": {
                    "company_name": {"type": "string"},
                    "industry": {"type": "string"},
                    "region": {"type": "string"},
                    "level": {"type": "string", "enum": ["S", "A", "B", "C", "D"], "description": "客户等级"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_customers",
            "description": "搜索客户信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词（公司名）"},
                    "level": {"type": "string", "enum": ["S", "A", "B", "C", "D"]},
                    "page": {"type": "integer", "default": 1},
                    "size": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_360",
            "description": "获取客户360度视图，包含关联的线索、商机、活动等完整信息。",
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_opportunity",
            "description": "创建商机，关联到客户。",
            "parameters": {
                "type": "object",
                "required": ["name", "customer_id"],
                "properties": {
                    "name": {"type": "string", "description": "商机名称"},
                    "customer_id": {"type": "string"},
                    "amount": {"type": "number", "description": "预计金额(元)"},
                    "expected_close_date": {"type": "string", "description": "预计成交日期 (YYYY-MM-DD)"},
                    "product_type": {"type": "string", "enum": ["standard", "custom"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_opportunities",
            "description": "搜索商机。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "stage": {"type": "string", "enum": ["initial_contact", "needs_confirmed", "solution_review", "negotiation", "won", "lost"]},
                    "page": {"type": "integer", "default": 1},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_opportunity_stage",
            "description": "推进商机阶段（阶段只能向前推进，丢单可从任意阶段）。",
            "parameters": {
                "type": "object",
                "required": ["opportunity_id", "new_stage"],
                "properties": {
                    "opportunity_id": {"type": "string"},
                    "new_stage": {"type": "string", "enum": ["initial_contact", "needs_confirmed", "solution_review", "negotiation", "won", "lost"]},
                    "lost_reason": {"type": "string", "description": "丢单原因（new_stage=lost时必填）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_activity",
            "description": "记录销售活动（拜访、电话、邮件、会议、备注）。",
            "parameters": {
                "type": "object",
                "required": ["type", "subject"],
                "properties": {
                    "type": {"type": "string", "enum": ["call", "visit", "email", "meeting", "note"]},
                    "subject": {"type": "string", "description": "活动主题"},
                    "content": {"type": "string", "description": "活动详情"},
                    "customer_id": {"type": "string"},
                    "opportunity_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_activities",
            "description": "查询活动记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "opportunity_id": {"type": "string"},
                    "type": {"type": "string", "enum": ["call", "visit", "email", "meeting", "note"]},
                    "page": {"type": "integer", "default": 1},
                },
            },
        },
    },
]
