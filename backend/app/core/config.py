import base64
import json
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Hermes Pro API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    ai_provider: str = Field(default="stub", validation_alias="AI_PROVIDER")
    ai_fallback_provider: str = Field(default="openai", validation_alias="AI_FALLBACK_PROVIDER")
    ai_api_key: str | None = Field(default=None, validation_alias="AI_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-6-luna", validation_alias="OPENAI_CHAT_MODEL")
    openai_agent_model: str = Field(default="gpt-6-astra", validation_alias="OPENAI_AGENT_MODEL")
    autonomy_enabled: bool = Field(default=False, validation_alias="AUTONOMY_ENABLED")
    embedded_worker_enabled: bool = Field(default=False, validation_alias="EMBEDDED_WORKER_ENABLED")
    autonomy_interval_seconds: int = Field(default=900, validation_alias="AUTONOMY_INTERVAL_SECONDS")
    autonomy_max_daily_products: int = Field(default=3, ge=0, le=100, validation_alias="AUTONOMY_MAX_DAILY_PRODUCTS")
    autonomy_max_active_products: int = Field(default=1, ge=1, le=20, validation_alias="AUTONOMY_MAX_ACTIVE_PRODUCTS")
    autonomy_max_ready_to_publish: int = Field(default=3, ge=0, le=100, validation_alias="AUTONOMY_MAX_READY_TO_PUBLISH")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash", validation_alias="GEMINI_MODEL")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_secret_key: str | None = Field(default=None, validation_alias="SUPABASE_SECRET_KEY")
    supabase_service_role_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    hotmart_client_id: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_ID")
    hotmart_client_secret: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_SECRET")
    hotmart_webhook_token: str | None = Field(default=None, validation_alias="HOTMART_WEBHOOK_TOKEN")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")
    hermes_api_key: str | None = Field(default=None, validation_alias="HERMES_API_KEY")

    @field_validator("autonomy_interval_seconds")
    @classmethod
    def validate_autonomy_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("AUTONOMY_INTERVAL_SECONDS must be at least 60")
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def get_supabase_server_key(settings: Settings) -> str | None:
    """Return only a Supabase server credential; never fall back to anon/publishable keys."""
    candidates = (settings.supabase_service_role_key, settings.supabase_secret_key)
    for key in candidates:
        if not key:
            continue
        if key.startswith("sb_secret_"):
            return key
        if key.startswith("eyJ") and key.count(".") >= 2:
            try:
                payload = key.split(".")[1]
                payload += "=" * (-len(payload) % 4)
                claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
                if claims.get("role") == "service_role":
                    return key
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
    return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
