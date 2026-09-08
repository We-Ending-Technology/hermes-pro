from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Hermes Pro API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    ai_provider: str = "stub"
    ai_api_key: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
