"""CRM 后端配置模块。

从环境变量或 .env 文件中加载配置，提供数据库、Redis 及应用层面的设置。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """CRM 应用配置。

    优先从环境变量读取，其次从 .env 文件读取，最后使用默认值。
    """

    # ── 应用 ──
    APP_NAME: str = "Sirus AI-CRM"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    APP_PORT: int = 8900

    # ── 数据库 (PostgreSQL 16 + pgvector) ──
    DATABASE_URL: str = (
        "postgresql+asyncpg://ai_crm:ai_crm_2026@172.16.12.50:5432/ai_crm"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO: bool = False

    # ── Redis 7 ──
    REDIS_URL: str = "redis://172.16.12.50:6379/0"

    # ── JWT (Sprint 3-4 启用) ──
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 小时

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
