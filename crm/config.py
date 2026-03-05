from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://ai_crm:ai_crm_2026@localhost:5432/ai_crm"
    REDIS_URL: str = "redis://localhost:6379/0"
    APP_PORT: int = 8900

    class Config:
        env_file = ".env"


settings = Settings()
