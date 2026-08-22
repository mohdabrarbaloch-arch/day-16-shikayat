"""Application configuration — all secrets come from environment variables only."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Shikayat"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./shikayat.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # CORS
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000,https://shikayat.vercel.app"

    # Reopen rule
    REOPEN_WINDOW_DAYS: int = 14
    MAX_REOPENS: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
