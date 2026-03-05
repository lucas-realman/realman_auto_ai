"""Supervisor Agent — intent classification and routing."""

import json
import logging
import time
from typing import Any

from openai import AsyncOpenAI

from agent.config import settings
from agent.session import get_history

logger = logging.getLogger(__name__)

ROUTE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_agent",
            "description": "根据用户意图将消息路由到对应的子Agent处理。",
            "parameters": {
                "type": "object",
                "required": ["agent_name", "intent"],
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["sales_assistant", "lead_scoring", "customer_insight"],
                        "description": "目标子Agent",
                    },
                    "intent": {
                        "type": "string",
                        "description": "识别的用户意图",
                    },
                },
            },
        },
    },
]

SYSTEM_PROMPT = (
    "你是 Sirus AI CRM 的 Supervisor Agent。你的职责是分析用户消息的意图，"
    "然后将其路由到合适的子Agent处理。\n\n"
    "可用的子Agent:\n"
    "- sales_assistant: 处理线索管理、客户管理、商机管理、活动记录等CRM操作\n"
    "- lead_scoring: 线索评分（开发中）\n"
    "- customer_insight: 客户洞察分析（开发中）\n\n"
    "请调用 route_to_agent 函数来路由消息。对于日常CRM操作，路由到 sales_assistant。"
)


class SupervisorAgent:
    """Supervisor Agent — classifies intent and delegates to sub-agents."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url=settings.VLLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
        )
        self.model = settings.MODEL_NAME
        self._sales_assistant: Any = None

    def _get_sales_assistant(self) -> Any:
        """Lazy-load SalesAssistantAgent to avoid import errors during skeleton phase."""
        if self._sales_assistant is None:
            try:
                from agent.agents.sales_assistant import SalesAssistantAgent
                self._sales_assistant = SalesAssistantAgent()
            except Exception as exc:
                logger.warning("SalesAssistantAgent unavailable: %s", exc)
        return self._sales_assistant

    async def route(self, message: str, session_id: str) -> dict[str, Any]:
        start = time.time()

        history = await get_history(session_id, limit=5)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-5:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ROUTE_TOOLS,
                tool_choice="auto",
            )
            choice = resp.choices[0]

            agent_name = "sales_assistant"
            intent = "general_chat"

            if choice.message.tool_calls:
                tc = choice.message.tool_calls[0]
                args = json.loads(tc.function.arguments)
                agent_name = args.get("agent_name", "sales_assistant")
                intent = args.get("intent", "general_chat")
            elif choice.message.content:
                agent_name = "sales_assistant"
                intent = "general_chat"

        except Exception:
            logger.exception("Supervisor routing failed, defaulting to sales_assistant")
            agent_name = "sales_assistant"
            intent = "general_chat"

        sales_assistant = self._get_sales_assistant()
        if agent_name == "sales_assistant" and sales_assistant is not None:
            result = await sales_assistant.handle(message, session_id)
        elif agent_name == "sales_assistant" and sales_assistant is None:
            # Fallback when SalesAssistantAgent is not yet implemented
            result = {
                "reply": f"收到您的消息：{message}",
                "tool_calls": [],
                "agent_used": "supervisor",
                "model_used": f"local/{self.model}",
            }
        elif agent_name in ("lead_scoring", "customer_insight"):
            result = {
                "reply": f"「{agent_name}」功能开发中，敬请期待！",
                "tool_calls": [],
                "agent_used": agent_name,
                "model_used": f"local/{self.model}",
            }
        else:
            if sales_assistant is not None:
                result = await sales_assistant.handle(message, session_id)
            else:
                result = {
                    "reply": f"收到您的消息：{message}",
                    "tool_calls": [],
                    "agent_used": "supervisor",
                    "model_used": f"local/{self.model}",
                }

        latency_ms = int((time.time() - start) * 1000)
        result["intent"] = intent
        result["latency_ms"] = latency_ms
        if "agent_used" not in result:
            result["agent_used"] = agent_name

        return result
