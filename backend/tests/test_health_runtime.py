from backend.app.core.config import Settings


def test_settings_never_exposes_secret_values_in_runtime_status_shape():
    settings = Settings(GEMINI_API_KEY="secret", SUPABASE_URL="https://example.supabase.co", SUPABASE_SECRET_KEY="service-secret", AI_PROVIDER="gemini")
    assert settings.ai_configured is True
    status = {
        "ai": settings.ai_configured,
        "ai_provider": settings.effective_ai_provider,
        "supabase_configured": bool(settings.supabase_url and settings.supabase_secret_key),
    }
    assert "secret" not in str(status)
    assert "service-secret" not in str(status)
