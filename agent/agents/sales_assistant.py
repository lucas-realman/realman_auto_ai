"""Sales Assistant Agent — handles CRM tool-calling via vLLM."""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from agent.config import settings
from agent.session import get_history, save_message
from agent.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class SalesAssistantAgent:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url=settings.VLLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
        )
        self.model = settings.MODEL_NAME

    async def handle(self, message: str, session_id: str) -> dict[str, Any]:
        history = await get_history(session_id, limit=20)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Sirus AI CRM 的销售助手。帮助用户管理线索、客户、商机和活动。"
                    "根据用户的请求调用合适的工具完成操作，并用自然语言总结结果。"
                ),
            },
        ]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        tool_calls_log: list[dict] = []
        max_rounds = 5

        for _ in range(max_rounds):
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls" or (
                choice.message.tool_calls
            ):
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    logger.info("Tool call: %s(%s)", fn_name, fn_args)

                    fn = TOOL_FUNCTIONS.get(fn_name)
                    if fn is None:
                        result = {"error": f"Unknown tool: {fn_name}"}
                    else:
                        try:
                            result = await fn(**fn_args)
                        except Exception as e:
                            logger.exception("Tool %s failed", fn_name)
                            result = {"error": str(e)}

                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    tool_calls_log.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result_summary": result_str[:200],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
            else:
                reply = choice.message.content or ""
                return {
                    "reply": reply,
                    "tool_calls": tool_calls_log,
                    "agent_used": "sales_assistant",
                    "model_used": f"local/{self.model}",
                }

        return {
            "reply": "抱歉，我在处理您的请求时遇到了问题，请稍后重试。",
            "tool_calls": tool_calls_log,
            "agent_used": "sales_assistant",
            "model_used": f"local/{self.model}",
        }
