from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """DingTalk机器人配置"""

    # CRM API 配置（bot_server.py 引用 settings.crm_api_base）
    crm_api_base: str = "http://172.16.12.50:8900"

    # DingTalk 应用配置
    dingtalk_app_key: str = "dingdebpmryxshlgpdc6"
    dingtalk_app_secret: str = "yE2Os-wytZCGU9Ul4L8FTNIDl9tGElaSEF0E_MrvJvtM0FDkO5ZC7hmOmqXgpoJO"
    dingtalk_robot_code: str = "dingdebpmryxshlgpdc6"
    dingtalk_app_id: str = "0214c074-c7b8-4b0c-9904-85da31849ad8"
    dingtalk_agent_id: str = "4303248408"

    # 服务配置（bot_server.py 引用 settings.bot_port）
    bot_port: int = 9000
    bot_host: str = "0.0.0.0"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
