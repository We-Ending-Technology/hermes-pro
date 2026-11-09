import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, settings


@pytest.fixture(autouse=True)
def configure_test_api_key(monkeypatch):
    monkeypatch.setattr(settings, "hermes_api_key", "test-hermes-key")


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnostic_agent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/run",
            json={"agent": "diagnostic", "input": {"prompt": "hello"}},
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["output"]["provider"] == "stub"


def test_unknown_agent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agents/run",
            json={"agent": "unknown", "input": {}},
            headers={"X-Hermes-API-Key": "test-hermes-key"},
        )
    assert response.status_code == 404
