from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


CURRENT_GEMINI_MODEL = "gemini-3.6-flash"
LEGACY_GEMINI_MODELS = {"gemini-2.5-flash"}


class Settings(BaseSettings):
    app_name: str = "Hermes Pro API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    ai_provider: str = Field(default="auto", validation_alias="AI_PROVIDER")
    ai_provider_order: str = Field(default="gemini,openai", validation_alias="AI_PROVIDER_ORDER")
    ai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("AI_API_KEY", "AI_GATEWAY_API_KEY"))
    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))
    openai_api_keys: str = Field(default="", validation_alias="OPENAI_API_KEYS")
    openai_model: str = Field(default="gpt-5.6-luna", validation_alias="OPENAI_MODEL")
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"))
    gemini_api_keys: str = Field(default="", validation_alias="GEMINI_API_KEYS")
    gemini_model: str = Field(default=CURRENT_GEMINI_MODEL, validation_alias=AliasChoices("GEMINI_MODEL", "GOOGLE_GEMINI_MODEL"))
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "SUPABASE_PROJECT_URL", "SUPABASE_HOST"))
    supabase_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE", "SUPABASE_SECRET", "SUPABASE_KEY"))
    supabase_internal_api_key: str | None = Field(default=None, validation_alias=AliasChoices("HERMES_SUPABASE_INTERNAL_KEY", "SUPABASE_INTERNAL_API_KEY"))
    redis_url: str = Field(default="", validation_alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173,https://hermes-pro-command-center.onrender.com,https://hermes-pro.vercel.app", validation_alias="CORS_ORIGINS")
    hotmart_client_id: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_ID")
    hotmart_client_secret: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_SECRET")
    hotmart_webhook_token: str | None = Field(default=None, validation_alias="HOTMART_WEBHOOK_TOKEN")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        model = value.strip()
        if model in LEGACY_GEMINI_MODELS:
            raise ValueError(f"{model} is no longer supported; use {CURRENT_GEMINI_MODEL}")
        return model

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @staticmethod
    def _split_secrets(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def gemini_api_key_pool(self) -> list[str]:
        keys = self._split_secrets(self.gemini_api_keys)
        if self.gemini_api_key and self.gemini_api_key not in keys:
            keys.insert(0, self.gemini_api_key)
        return keys

    @property
    def openai_api_key_pool(self) -> list[str]:
        keys = self._split_secrets(self.openai_api_keys)
        if self.openai_api_key and self.openai_api_key not in keys:
            keys.insert(0, self.openai_api_key)
        return keys

    @property
    def provider_order_list(self) -> list[str]:
        return [item.strip().lower() for item in self.ai_provider_order.split(",") if item.strip()]

    @property
    def effective_ai_provider(self) -> str:
        requested = (self.ai_provider or "auto").strip().lower()
        if requested in {"gemini", "openai"}:
            pools = {"gemini": self.gemini_api_key_pool, "openai": self.openai_api_key_pool}
            if pools[requested]:
                return requested
            for provider in self.provider_order_list:
                if pools.get(provider):
                    return provider
            return "unconfigured"
        pools = {"gemini": self.gemini_api_key_pool, "openai": self.openai_api_key_pool}
        for provider in self.provider_order_list:
            if pools.get(provider):
                return provider
        if requested == "stub":
            return "stub"
        return "unconfigured"

    @property
    def ai_configured(self) -> bool:
        return self.effective_ai_provider in {"gemini", "openai", "stub"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
