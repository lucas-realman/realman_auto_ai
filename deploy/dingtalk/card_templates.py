from typing import Dict, Any, List, Optional
import json


class CardTemplates:
    """DingTalk交互式卡片模板"""
    
    @staticmethod
    def lead_card(lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        线索信息卡片
        
        显示线索详情 + 转化/跟进按钮
        """
        return {
            "version": "1.0",
            "type": "card",
            "modules": [
                {
                    "type": "header",
                    "data": {
                        "title": {
                            "type": "plain_text",
                            "content": f"线索：{lead_data.get('company_name', 'N/A')}"
                        },
                        "subtitle": {
                            "type": "plain_text",
                            "content": f"状态：{lead_data.get('status', '新建')}"
                        }
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "markdown",
                        "content": f"""**公司名称**：{lead_data.get('company_name', 'N/A')}
**联系人**：{lead_data.get('contact_name', 'N/A')}
**手机号**：{lead_data.get('phone', 'N/A')}
**邮箱**：{lead_data.get('email', 'N/A')}
**创建时间**：{lead_data.get('created_at', 'N/A')}"""
                    }
                },
                {
                    "type": "action_group",
                    "actions": [
                        {
                            "type": "button",
                            "text": "转化为客户",
                            "value": f"convert_lead_{lead_data.get('id', '')}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": "跟进",
                            "value": f"follow_up_lead_{lead_data.get('id', '')}",
                            "style": "default"
                        }
                    ]
                }
            ]
        }
    
    @staticmethod
    def customer_card(customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        客户360视图卡片
        """
        return {
            "version": "1.0",
            "type": "card",
            "modules": [
                {
                    "type": "header",
                    "data": {
                        "title": {
                            "type": "plain_text",
                            "content": f"客户：{customer_data.get('name', 'N/A')}"
                        },
                        "subtitle": {
                            "type": "plain_text",
                            "content": f"等级：{customer_data.get('level', '普通')}"
                        }
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "markdown",
                        "content": f"""**客户名称**：{customer_data.get('name', 'N/A')}
**行业**：{customer_data.get('industry', 'N/A')}
**规模**：{customer_data.get('size', 'N/A')}
**主要联系人**：{customer_data.get('primary_contact', 'N/A')}
**年度合同额**：{customer_data.get('annual_contract_value', '0')}
**最后交互**：{customer_data.get('last_interaction', 'N/A')}"""
                    }
                },
                {
                    "type": "action_group",
                    "actions": [
                        {
                            "type": "button",
                            "text": "查看商机",
                            "value": f"view_opportunities_{customer_data.get('id', '')}",
                            "style": "default"
                        },
                        {
                            "type": "button",
                            "text": "新建商机",
                            "value": f"create_opportunity_{customer_data.get('id', '')}",
                            "style": "primary"
                        }
                    ]
                }
            ]
        }
    
    @staticmethod
    def opportunity_card(opp_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        商机卡片
        
        显示商机详情 + 阶段推进按钮
        """
        return {
            "version": "1.0",
            "type": "card",
            "modules": [
                {
                    "type": "header",
                    "data": {
                        "title": {
                            "type": "plain_text",
                            "content": f"商机：{opp_data.get('name', 'N/A')}"
                        },
                        "subtitle": {
                            "type": "plain_text",
                            "content": f"阶段：{opp_data.get('stage', 'N/A')}"
                        }
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "markdown",
                        "content": f"""**商机名称**：{opp_data.get('name', 'N/A')}
**客户**：{opp_data.get('customer_name', 'N/A')}
**金额**：{opp_data.get('amount', '0')}
**阶段**：{opp_data.get('stage', 'N/A')}
**预计成交日期**：{opp_data.get('expected_close_date', 'N/A')}
**成功概率**：{opp_data.get('probability', '0')}%"""
                    }
                },
                {
                    "type": "action_group",
                    "actions": [
                        {
                            "type": "button",
                            "text": "推进阶段",
                            "value": f"advance_stage_{opp_data.get('id', '')}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": "添加活动",
                            "value": f"add_activity_{opp_data.get('id', '')}",
                            "style": "default"
                        }
                    ]
                }
            ]
        }
    
    @staticmethod
    def confirm_card(action: str, entity_id: str, message: str) -> Dict[str, Any]:
        """
        操作确认卡片
        """
        action_text_map = {
            "convert_lead": "转化线索",
            "delete_lead": "删除线索",
            "close_opportunity": "关闭商机",
            "win_opportunity": "赢单"
        }
        
        return {
            "version": "1.0",
            "type": "card",
            "modules": [
                {
                    "type": "header",
                    "data": {
                        "title": {
                            "type": "plain_text",
                            "content": "确认操作"
                        }
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "markdown",
                        "content": f"**操作**：{action_text_map.get(action, action)}\n\n{message}"
                    }
                },
                {
                    "type": "action_group",
                    "actions": [
                        {
                            "type": "button",
                            "text": "确认",
                            "value": f"confirm_{action}_{entity_id}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": "取消",
                            "value": f"cancel_{action}_{entity_id}",
                            "style": "default"
                        }
                    ]
                }
            ]
        }
    
    @staticmethod
    def help_card() -> Dict[str, Any]:
        """
        帮助卡片
        """
        return {
            "version": "1.0",
            "type": "card",
            "modules": [
                {
                    "type": "header",
                    "data": {
                        "title": {
                            "type": "plain_text",
                            "content": "DingTalk CRM机器人帮助"
                        }
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "markdown",
                        "content": """**支持的命令：**

📋 **查线索** XX公司
查询线索信息

➕ **新建线索** 公司名 联系人 手机号
创建新线索

👤 **客户详情** XX
查看客户360视图

💼 **推进商机** XX
查看商机并推进阶段

📊 **最近活动**
查看最近的CRM活动

❓ **帮助**
显示此帮助信息"""
                    }
                }
            ]
        }
