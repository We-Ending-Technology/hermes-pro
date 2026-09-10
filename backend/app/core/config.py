from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Hermes Pro API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_secret_key: str | None = None
    ai_provider: str = "stub"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    redis_url: str | None = None
    cors_origins: str = "http://localhost:5173"
    worker_enabled: bool = True
    max_job_retries: int = 3
    auto_production_enabled: bool = False
    auto_production_daily_limit: int = 1
    cover_provider: str = "none"
    cover_api_url: str | None = None
    storage_bucket: str = "ebooks"
    supabase_jobs_table: str = "hermes_jobs"
    supabase_products_table: str = "hermes_products"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and (self.supabase_service_role_key or self.supabase_secret_key))

    @property
    def supabase_key(self) -> str | None:
        return self.supabase_service_role_key or self.supabase_secret_key

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

@lru_cache
def get_settings() -> Settings:
    return Settings()
