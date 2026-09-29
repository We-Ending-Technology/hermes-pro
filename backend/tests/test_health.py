from fastapi.testclient import TestClient

from app.main import app


def test_health_is_liveness_probe():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_never_exposes_secret_values(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded"}
    assert "checks" in payload
    assert all("configured" in item and "message" in item for item in payload["checks"])
