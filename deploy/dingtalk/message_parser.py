from typing import Dict, Any, Optional
import re


class MessageParser:
    """DingTalk消息意图解析器"""
    
    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        """
        解析DingTalk消息文本，提取意图和参数
        
        支持的命令：
        - 查线索 XX公司
        - 新建线索 公司名 联系人 手机号
        - 客户详情 XX
        - 推进商机 XX
        - 最近活动
        - 帮助/help
        """
        text = text.strip()
        
        # 查线索
        if text.startswith("查线索"):
            keyword = text.replace("查线索", "").strip()
            return {
                "action": "search_lead",
                "params": {"keyword": keyword}
            }
        
        # 新建线索
        if text.startswith("新建线索"):
            parts = text.replace("新建线索", "").strip().split()
            if len(parts) >= 3:
                return {
                    "action": "create_lead",
                    "params": {
                        "company_name": parts[0],
                        "contact_name": parts[1],
                        "phone": parts[2]
                    }
                }
            return {
                "action": "error",
                "params": {"message": "新建线索格式错误，请使用：新建线索 公司名 联系人 手机号"}
            }
        
        # 客户详情
        if text.startswith("客户详情"):
            keyword = text.replace("客户详情", "").strip()
            return {
                "action": "customer_detail",
                "params": {"keyword": keyword}
            }
        
        # 推进商机
        if text.startswith("推进商机"):
            keyword = text.replace("推进商机", "").strip()
            return {
                "action": "advance_opportunity",
                "params": {"keyword": keyword}
            }
        
        # 最近活动
        if text == "最近活动":
            return {
                "action": "recent_activities",
                "params": {}
            }
        
        # 帮助
        if text in ["帮助", "help"]:
            return {
                "action": "help",
                "params": {}
            }
        
        # 默认
        return {
            "action": "unknown",
            "params": {"message": text}
        }


# ---------- compatibility layer for bot_server.py ----------
from enum import Enum

class Intent(str, Enum):
    LIST_LEADS = "list_leads"
    SEARCH_CUSTOMER = "search_customer"
    CREATE_LEAD = "create_lead"
    OPPORTUNITY_INFO = "opportunity_info"
    CONVERT_LEAD = "convert_lead"
    HELP = "help"
    UNKNOWN = "unknown"

_ACTION_MAP = {
    "search_lead": Intent.LIST_LEADS,
    "create_lead": Intent.CREATE_LEAD,
    "customer_detail": Intent.SEARCH_CUSTOMER,
    "advance_opportunity": Intent.OPPORTUNITY_INFO,
    "recent_activities": Intent.LIST_LEADS,
    "help": Intent.HELP,
    "unknown": Intent.UNKNOWN,
    "error": Intent.UNKNOWN,
}

def parse_intent(text: str):
    """Adapter: returns (Intent, params_dict) for bot_server.py"""
    result = MessageParser.parse(text)
    action = result.get("action", "unknown")
    intent = _ACTION_MAP.get(action, Intent.UNKNOWN)
    params = result.get("params", {})
    return intent, params
