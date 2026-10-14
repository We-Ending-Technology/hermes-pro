from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.ai_gateway.stub import StubAIGateway


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnostic_agent(monkeypatch) -> None:
    import backend.app.main as main_module
    original = main_module.ai_gateway
    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")
    main_module.ai_gateway = StubAIGateway()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/agents/run",
                headers={"X-Hermes-API-Key": "test-token"},
                json={"agent": "diagnostic", "input": {"prompt": "hello"}},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["output"]["provider"] == "stub"
    finally:
        main_module.ai_gateway = original


def test_unknown_agent(monkeypatch) -> None:
    import backend.app.main as main_module
    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/run",
            headers={"X-Hermes-API-Key": "test-token"},
            json={"agent": "unknown", "input": {}},
        )
    assert response.status_code == 404
