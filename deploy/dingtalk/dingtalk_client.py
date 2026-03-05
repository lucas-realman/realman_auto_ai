import httpx
import hashlib
import hmac
import base64
import time
from typing import Dict, Any, Optional
from functools import lru_cache
import asyncio


class DingTalkClient:
    """DingTalk Open API客户端"""
    
    DINGTALK_API_BASE = "https://api.dingtalk.com"
    TOKEN_CACHE_TIME = 7200  # 2小时
    
    def __init__(self, app_key: str, app_secret: str, client: httpx.AsyncClient):
        self.app_key = app_key
        self.app_secret = app_secret
        self.client = client
        self._token_cache: Optional[Dict[str, Any]] = None
        self._token_expire_time = 0
    
    async def get_access_token(self) -> str:
        """
        获取DingTalk访问令牌（带缓存）
        """
        current_time = time.time()
        
        # 检查缓存是否有效
        if self._token_cache and current_time < self._token_expire_time:
            return self._token_cache.get("access_token", "")
        
        # 获取新令牌
        url = f"{self.DINGTALK_API_BASE}/v1.0/oauth2/accessToken"
        payload = {
            "appKey": self.app_key,
            "appSecret": self.app_secret
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # 缓存令牌
            self._token_cache = data
            self._token_expire_time = current_time + self.TOKEN_CACHE_TIME
            
            return data.get("access_token", "")
        except Exception as e:
            print(f"获取DingTalk令牌失败: {e}")
            return ""
    
    async def send_markdown_message(
        self,
        chat_id: str,
        title: str,
        text: str
    ) -> bool:
        """
        发送Markdown格式消息
        """
        token = await self.get_access_token()
        if not token:
            return False
        
        url = f"{self.DINGTALK_API_BASE}/v1.0/robot/oToMessages/asyncSend"
        
        payload = {
            "robotCode": self.app_key,
            "userIds": [chat_id],
            "msgKey": "sampleMarkdown",
            "msgParam": {
                "title": title,
                "text": text
            }
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"发送Markdown消息失败: {e}")
            return False
    
    async def send_card_message(
        self,
        chat_id: str,
        card_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        发送交互式卡片消息
        
        返回卡片ID
        """
        token = await self.get_access_token()
        if not token:
            return None
        
        url = f"{self.DINGTALK_API_BASE}/v1.0/robot/oToMessages/asyncSend"
        
        payload = {
            "robotCode": self.app_key,
            "userIds": [chat_id],
            "msgKey": "sampleCard",
            "msgParam": card_data
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("processQueryKey")
        except Exception as e:
            print(f"发送卡片消息失败: {e}")
            return None
    
    async def update_card(
        self,
        card_id: str,
        card_data: Dict[str, Any]
    ) -> bool:
        """
        更新交互式卡片内容
        """
        token = await self.get_access_token()
        if not token:
            return False
        
        url = f"{self.DINGTALK_API_BASE}/v1.0/robot/interactiveCards/update"
        
        payload = {
            "outTrackId": card_id,
            "cardData": card_data
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = await self.client.put(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"更新卡片失败: {e}")
            return False
