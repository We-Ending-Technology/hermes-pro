from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Hermes Pro API"
    app_env: str = "development"
    hermes_api_token: str | None = Field(default=None, validation_alias="HERMES_API_TOKEN")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    ai_provider: str = Field(default="gemini", validation_alias="AI_PROVIDER")
    ai_api_key: str | None = Field(default=None, validation_alias="AI_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.6-luna", validation_alias="OPENAI_MODEL")
    openai_agent_model: str = Field(default="gpt-6-astra", validation_alias="OPENAI_AGENT_MODEL")
    autonomy_interval_seconds: int = Field(default=900, validation_alias="AUTONOMY_INTERVAL_SECONDS")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    # Honor the key the operator updates in Render first; stale alias variables can otherwise shadow it.
    supabase_secret_key: str | None = Field(default=None, validation_alias="SUPABASE_SECRET_KEY")
    supabase_service_role_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_service_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_KEY")
    # Diagnostic-only aliases: these are never accepted for privileged writes.
    supabase_key: str | None = Field(default=None, validation_alias="SUPABASE_KEY")
    supabase_anon_key: str | None = Field(default=None, validation_alias="SUPABASE_ANON_KEY")
    supabase_publishable_key: str | None = Field(default=None, validation_alias="SUPABASE_PUBLISHABLE_KEY")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    hotmart_client_id: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_ID")
    hotmart_client_secret: str | None = Field(default=None, validation_alias="HOTMART_CLIENT_SECRET")
    hotmart_webhook_token: str | None = Field(default=None, validation_alias="HOTMART_WEBHOOK_TOKEN")
    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")
    freelancer_access_token: str | None = Field(default=None, validation_alias="FREELANCER_ACCESS_TOKEN")
    freelancer_sandbox: bool = Field(default=True, validation_alias="FREELANCER_SANDBOX")
    freelancer_enabled: bool = Field(default=False, validation_alias="FREELANCER_ENABLED")
    freelancer_auto_apply: bool = Field(default=False, validation_alias="FREELANCER_AUTO_APPLY")
    freelancer_bidder_id: int | None = Field(default=None, validation_alias="FREELANCER_BIDDER_ID")
    freelancer_profile_id: int | None = Field(default=None, validation_alias="FREELANCER_PROFILE_ID")
    canva_client_id: str | None = Field(default=None, validation_alias="CANVA_CLIENT_ID")
    canva_client_secret: str | None = Field(default=None, validation_alias="CANVA_CLIENT_SECRET")
    canva_redirect_uri: str | None = Field(default=None, validation_alias="CANVA_REDIRECT_URI")
    autonomy_enabled: bool = Field(default=True, validation_alias="AUTONOMY_ENABLED")
    autonomy_min_score: int = Field(default=55, validation_alias="AUTONOMY_MIN_SCORE")
    # Side effects stay disabled until the owner explicitly enables them in the deployment.
    autonomy_kill_switch: bool = Field(default=False, validation_alias="AUTONOMY_KILL_SWITCH")
    external_actions_enabled: bool = Field(default=False, validation_alias="EXTERNAL_ACTIONS_ENABLED")
    freelancer_max_bid_brl: float = Field(default=0, ge=0, validation_alias="FREELANCER_MAX_BID_BRL")
    autonomy_max_concurrent_jobs: int = Field(default=2, ge=1, le=2, validation_alias="AUTONOMY_MAX_CONCURRENT_JOBS")
    autonomy_max_retries: int = Field(default=3, ge=0, le=3, validation_alias="AUTONOMY_MAX_RETRIES")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
