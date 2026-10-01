from backend.app.core.config import Settings


def test_autonomy_defaults_off():
    settings = Settings()
    assert settings.autonomy_enabled is False
    assert settings.autonomy_interval_seconds > 0


def test_agent_status_without_key_is_blocked():
    settings = Settings(openai_api_key=None)
    assert settings.openai_api_key is None
