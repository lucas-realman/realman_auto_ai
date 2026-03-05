"""Agent engine configuration.

Centralised settings for the Agent Engine.  All values can be overridden
via environment variables or a ``.env`` file in the project root.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime settings for the Sirus Agent Engine."""

    # ── LLM / vLLM ──
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    OPENAI_API_KEY: str = "EMPTY"
    MODEL_NAME: str = "qwen3-30b-a3b"

    # ── Redis (shared with CRM) ──
    REDIS_URL: str = "redis://172.16.12.50:6379/0"

    # ── CRM backend ──
    CRM_BASE_URL: str = "http://172.16.12.50:8900/api/v1"

    # ── Application ──
    APP_PORT: int = 8100
    LOG_LEVEL: str = "INFO"

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
