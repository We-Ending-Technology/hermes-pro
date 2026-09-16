from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.ai_gateway.stub import StubAIGateway


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnostic_agent() -> None:
    previous = app.state.test_ai_gateway if hasattr(app.state, "test_ai_gateway") else None
    import backend.app.main as main_module
    original = main_module.ai_gateway
    main_module.ai_gateway = StubAIGateway()
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/agents/run", json={"agent": "diagnostic", "input": {"prompt": "hello"}})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["output"]["provider"] == "stub"
    finally:
        main_module.ai_gateway = original


def test_unknown_agent() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/agents/run", json={"agent": "unknown", "input": {}})
    assert response.status_code == 404
