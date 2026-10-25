from functools import lru_cache
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

ENV_FILE = (
    BACKEND_DIR
    / ".env"
)


class Settings(BaseSettings):
    environment: str = "development"

    supabase_url: str
    supabase_secret_key: str

    frontend_url: str = "http://localhost:3000"
    admin_url: str = "http://localhost:3001"


    # ------------------------------------------------------------------
    # Phase 9 - Smart Cart background worker
    # ------------------------------------------------------------------

    smart_cart_worker_enabled: bool = True

    smart_cart_worker_interval_seconds: int = 2


    # ------------------------------------------------------------------
    # Phase 10 / Phase 17 - Notifications
    # ------------------------------------------------------------------

    notification_worker_enabled: bool = True

    notification_worker_interval_seconds: int = 5

    notification_batch_size: int = 20

    notification_max_attempts: int = 5

    notification_backoff_seconds: int = 30

    notification_stale_processing_seconds: int = 300


    # ------------------------------------------------------------------
    # Phase 17 - Scheduler
    # ------------------------------------------------------------------

    scheduler_enabled: bool = True

    promotion_activation_interval_seconds: int = 60

    reservation_expiry_interval_seconds: int = 30

    job_health_stale_multiplier: int = 3


    # ------------------------------------------------------------------
    # Phase 12 - Cross-conversation memory
    # ------------------------------------------------------------------

    memory_stale_days: int = 90

    memory_stale_confidence_multiplier: float = 0.5


    # ------------------------------------------------------------------
    # Local Ollama LLM
    # ------------------------------------------------------------------

    ollama_url: str = "http://localhost:11434"

    ollama_llm_model: str = "qwen3:1.7b"

    ollama_llm_timeout_seconds: float = 60.0

    ollama_keep_alive: str = "30m"


    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    # "log" for development
    # "smtp" for real email delivery

    email_backend: str = "log"

    smtp_host: str = ""

    smtp_port: int = 587

    smtp_username: str = ""

    smtp_password: str = ""

    smtp_use_tls: bool = True

    email_from: str = (
        "Retailigent <no-reply@retailigent.local>"
    )


    # ------------------------------------------------------------------
    # Pydantic settings configuration
    # ------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=str(
            ENV_FILE
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()