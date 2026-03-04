"""Agent engine configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    REDIS_URL: str = "redis://172.16.12.50:6379/0"
    OPENAI_API_KEY: str = "EMPTY"
    MODEL_NAME: str = "qwen3-30b-a3b"
    APP_PORT: int = 8100
    CRM_BASE_URL: str = "http://172.16.12.50:8900/api/v1"

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
