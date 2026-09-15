from datetime import datetime

from backend.app.main import chat
from backend.app.schemas import ChatRequest


async def test_chat_current_date_does_not_require_ai(monkeypatch):
    monkeypatch.setattr("backend.app.main.ai_gateway", None)
    result = await chat(ChatRequest(message="QUE DIA É HOJE"))
    assert "2026" in result.response


async def test_chat_product_request_creates_job(monkeypatch):
    calls = []

    async def fake_create(request):
        calls.append(request.message)
        return {"response": "Job criado", "provider": "system", "model": "command"}

    monkeypatch.setattr("backend.app.main.handle_chat_command", fake_create)
    result = await chat(ChatRequest(message="produza um ebook sobre produtividade"))
    assert calls == ["produza um ebook sobre produtividade"]
    assert result.response == "Job criado"
