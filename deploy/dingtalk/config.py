from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """DingTalk机器人配置"""
    
    # CRM API配置
    CRM_API_URL: str = "http://172.16.12.50:8900"
    
    # DingTalk应用配置
    DINGTALK_APP_KEY: str = ""
    DINGTALK_APP_SECRET: str = ""
    DINGTALK_ROBOT_CODE: str = ""
    DINGTALK_CALLBACK_TOKEN: str = ""
    DINGTALK_AES_KEY: str = ""
    
    # 服务配置
    APP_PORT: int = 9000
    APP_HOST: str = "0.0.0.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
