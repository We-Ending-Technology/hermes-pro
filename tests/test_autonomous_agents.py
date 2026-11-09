from types import SimpleNamespace

import pytest

from backend.app.core.config import Settings
from backend.app.agents import orchestrator


def test_autonomy_defaults_off():
    settings = Settings()
    assert settings.autonomy_enabled is False
    assert settings.autonomy_interval_seconds > 0


def test_gemini_agent_configuration_does_not_require_openai_key():
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key="test-gemini-key",
        openai_api_key=None,
    )
    assert settings.gemini_api_key == "test-gemini-key"
    assert settings.openai_api_key is None


def test_gemini_default_model_is_current_flash():
    assert Settings().gemini_model == "gemini-3.8-flash"


class FakeGateway:
    def __init__(self):
        self.calls = []

    async def complete(self, prompt: str, *, system: str | None = None):
        self.calls.append((prompt, system))
        return SimpleNamespace(
            content=f"resultado-{len(self.calls)}",
            provider="gemini",
            model="test-model",
        )


@pytest.mark.asyncio
async def test_chief_runs_specialists_without_openai_credentials(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr(orchestrator, "build_ai_gateway", lambda settings: gateway)
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key="test-gemini-key",
        openai_api_key=None,
    )

    result = await orchestrator.run_chief("Diagnostique o sistema", settings)

    assert len(gateway.calls) == 5
    assert result["agent"] == "Hermes Chefe"
    assert result["steps"] == 5
    assert result["provider"] == "gemini"
    assert set(result["specialists"]) == {
        "Hermes Radar",
        "Hermes Factory",
        "Hermes Dev",
        "Hermes Analyst",
    }


@pytest.mark.asyncio
async def test_chief_rejects_stub_provider():
    settings = Settings(ai_provider="stub")
    with pytest.raises(RuntimeError, match="not a production AI provider"):
        await orchestrator.run_chief("Teste", settings)
