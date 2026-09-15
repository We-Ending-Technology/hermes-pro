from functools import lru_cache
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "GOOGLE_GEMINI_MODEL"))
    supabase_url: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_URL", "SUPABASE_PROJECT_URL", "SUPABASE_HOST"))
    supabase_secret_key: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE", "SUPABASE_SECRET", "SUPABASE_KEY"))
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    hotmart_client_id: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_ID")
    hotmart_client_secret: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_SECRET")
    hotmart_webhook_token: str | None = Field(default=None, validation_alias="HOTMART_WEBHOOK_TOKEN")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_ai_provider(self) -> str:
        requested = (self.ai_provider or "auto").strip().lower()
        if requested == "gemini":
            return "gemini" if self.gemini_api_key else "unconfigured"
        if requested == "openai":
            return "openai" if self.openai_api_key else "unconfigured"
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
