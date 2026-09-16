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
    ai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("AI_API_KEY", "AI_GATEWAY_API_KEY"))
    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))
    openai_model: str = Field(default="gpt-5.6-luna", validation_alias="OPENAI_MODEL")
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"))
    gemini_model: str = Field(default=CURRENT_GEMINI_MODEL, validation_alias=AliasChoices("GEMINI_MODEL", "GOOGLE_GEMINI_MODEL"))
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "SUPABASE_PROJECT_URL", "SUPABASE_HOST"))
    supabase_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE", "SUPABASE_SECRET", "SUPABASE_KEY"))
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

    @property
    def effective_ai_provider(self) -> str:
        requested = (self.ai_provider or "auto").strip().lower()
        if requested == "gemini":
            return "gemini" if self.gemini_api_key else "unconfigured"
        if requested == "openai":
            if self.openai_api_key:
                return "openai"
            if self.gemini_api_key:
                return "gemini"
            return "unconfigured"
        if self.gemini_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        if requested == "stub":
            return "stub"
        return "unconfigured"

    @property
    def ai_configured(self) -> bool:
        return self.effective_ai_provider in {"gemini", "openai", "stub"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
