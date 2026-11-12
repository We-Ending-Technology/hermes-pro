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
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_chat_model: str = Field(default="openai/gpt-oss-20b", validation_alias="GROQ_CHAT_MODEL")
    openai_agent_model: str = Field(default="gpt-6-astra", validation_alias="OPENAI_AGENT_MODEL")
    autonomy_enabled: bool = Field(default=False, validation_alias="AUTONOMY_ENABLED")
    embedded_worker_enabled: bool = Field(default=False, validation_alias="EMBEDDED_WORKER_ENABLED")
    autonomy_interval_seconds: int = Field(default=900, validation_alias="AUTONOMY_INTERVAL_SECONDS")
    autonomy_agent_interval_seconds: int = Field(default=3600, validation_alias="AUTONOMY_AGENT_INTERVAL_SECONDS")
    autonomy_max_daily_products: int = Field(default=3, ge=0, le=100, validation_alias="AUTONOMY_MAX_DAILY_PRODUCTS")
    autonomy_max_active_products: int = Field(default=1, ge=1, le=20, validation_alias="AUTONOMY_MAX_ACTIVE_PRODUCTS")
    autonomy_max_ready_to_publish: int = Field(default=3, ge=0, le=100, validation_alias="AUTONOMY_MAX_READY_TO_PUBLISH")
    autonomy_max_review_required_products: int = Field(default=3, ge=1, le=100, validation_alias="AUTONOMY_MAX_REVIEW_REQUIRED_PRODUCTS")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", validation_alias="GEMINI_MODEL")
    gemini_timeout_seconds: int = Field(default=45, ge=5, le=300, validation_alias="GEMINI_TIMEOUT_SECONDS")
    ai_image_provider: str = Field(default="ovhcloud", validation_alias="AI_IMAGE_PROVIDER")
    ai_image_required: bool = Field(default=True, validation_alias="AI_IMAGE_REQUIRED")
    ai_horde_api_key: str = Field(default="0000000000", validation_alias="AI_HORDE_API_KEY")
    ai_horde_model: str = Field(default="stable_diffusion_2.1", validation_alias="AI_HORDE_MODEL")
    ai_horde_base_url: str = Field(default="https://aihorde.net/api/v2", validation_alias="AI_HORDE_BASE_URL")
    ai_horde_timeout_seconds: int = Field(default=180, ge=30, le=900, validation_alias="AI_HORDE_TIMEOUT_SECONDS")
    ovhcloud_image_base_url: str = Field(default="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", validation_alias="OVHCLOUD_IMAGE_BASE_URL")
    ovhcloud_image_model: str = Field(default="stable-diffusion-xl-base-v10", validation_alias="OVHCLOUD_IMAGE_MODEL")
    ovhcloud_image_timeout_seconds: int = Field(default=90, ge=30, le=300, validation_alias="OVHCLOUD_IMAGE_TIMEOUT_SECONDS")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_secret_key: str | None = Field(default=None, validation_alias="SUPABASE_SECRET_KEY")
    supabase_service_role_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_publishable_key: str | None = Field(default=None, validation_alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_bridge_secret: str | None = Field(default=None, validation_alias="SUPABASE_BRIDGE_SECRET")
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    hotmart_client_id: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_ID")
    hotmart_client_secret: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_SECRET")
    hotmart_webhook_token: str | None = Field(default=None, validation_alias="HOTMART_WEBHOOK_TOKEN")
    kiwify_webhook_token: str | None = Field(default=None, validation_alias="KIWIFY_WEBHOOK_TOKEN")
    kiwify_api_client_id: str | None = Field(default=None, validation_alias="KIWIFY_API_CLIENT_ID")
    kiwify_api_client_secret: str | None = Field(default=None, validation_alias="KIWIFY_API_CLIENT_SECRET")
    kiwify_account_id: str | None = Field(default=None, validation_alias="KIWIFY_ACCOUNT_ID")
    hermes_public_api_url: str = Field(default="https://hermes-pro-api-commercial.onrender.com", validation_alias="HERMES_PUBLIC_API_URL")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")
    hermes_api_key: str | None = Field(default=None, validation_alias="HERMES_API_KEY")

    @field_validator("autonomy_interval_seconds")
    @classmethod
    def validate_autonomy_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("AUTONOMY_INTERVAL_SECONDS must be at least 60")
        return value

    @field_validator("autonomy_agent_interval_seconds")
    @classmethod
    def validate_autonomy_agent_interval(cls, value: int) -> int:
        if value < 300:
            raise ValueError("AUTONOMY_AGENT_INTERVAL_SECONDS must be at least 300")
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
