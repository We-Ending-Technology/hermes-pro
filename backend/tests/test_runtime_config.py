import os

import pytest

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


def test_default_gemini_model_is_current():
    settings = Settings(_env_file=None)
    assert settings.gemini_model == "gemini-3.6-flash"
    assert settings.gemini_model != "gemini-2.5-flash"


def test_legacy_gemini_model_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    with pytest.raises(ValueError, match="gemini-2.5-flash is no longer supported"):
        Settings()


def test_provider_key_pools_preserve_primary_key_and_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-primary")
    monkeypatch.setenv("GEMINI_API_KEYS", "gemini-primary,gemini-backup")
    monkeypatch.setenv("OPENAI_API_KEYS", "openai-primary,openai-backup")
    monkeypatch.setenv("AI_PROVIDER_ORDER", "gemini,openai")
    settings = Settings()
    assert settings.gemini_api_key_pool == ["gemini-primary", "gemini-backup"]
    assert settings.openai_api_key_pool == ["openai-primary", "openai-backup"]
    assert settings.provider_order_list == ["gemini", "openai"]
    assert settings.effective_ai_provider == "gemini"
