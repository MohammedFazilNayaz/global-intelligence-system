from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Global Intelligence Platform"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:@127.0.0.1:5432/global_intelligence"

    # Network / Collector Settings
    REQUEST_TIMEOUT_SECONDS: float = 15.0
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.5
    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    # V0.8 Deterministic Freshness Thresholds
    FRESHNESS_CURRENT_HOURS: int = 24       # <= 24 hours -> CURRENT
    FRESHNESS_RECENT_DAYS: int = 7          # <= 7 days -> RECENT
    FRESHNESS_STALE_DAYS: int = 30          # <= 30 days -> STALE, > 30 days -> HISTORICAL
    SOURCE_STALE_MULTIPLIER: float = 2.0    # age > polling_interval * multiplier -> STALE


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
