from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:localdev123@localhost:5432/telegram_agents"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    TELEGRAM_WEBHOOK_BASE_URL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
