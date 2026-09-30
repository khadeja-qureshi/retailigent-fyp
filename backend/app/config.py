from functools import lru_cache

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    environment: str = "development"

    supabase_url: str
    supabase_secret_key: str

    frontend_url: str = "http://localhost:3000"
    admin_url: str = "http://localhost:3001"

    # Phase 9 - Smart Cart background worker
    smart_cart_worker_enabled: bool = True
    smart_cart_worker_interval_seconds: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()