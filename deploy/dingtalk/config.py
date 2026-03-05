from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """DingTalk机器人配置"""

    # CRM API 配置（bot_server.py 引用 settings.crm_api_base）
    crm_api_base: str = "http://172.16.12.50:8900"

    # DingTalk 应用配置
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_robot_code: str = ""

    # 服务配置（bot_server.py 引用 settings.bot_port）
    bot_port: int = 9000
    bot_host: str = "0.0.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
