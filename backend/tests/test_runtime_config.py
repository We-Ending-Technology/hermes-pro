import os

from backend.app.core.config import Settings


def test_gemini_alias_is_resolved_without_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-gemini")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    settings = Settings()
    assert settings.gemini_api_key == "test-gemini"
    assert settings.effective_ai_provider == "gemini"


def test_supabase_service_role_alias_is_resolved(monkeypatch):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
    settings = Settings()
    assert settings.supabase_url == "https://example.supabase.co"
    assert settings.supabase_secret_key == "test-service-role"
