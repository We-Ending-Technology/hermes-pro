from fastapi.testclient import TestClient
from backend.app.main import app

def test_factory_flow_creates_job_and_product() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/factory/produce", json={"topic": "produtividade"})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        jobs = client.get("/api/v1/jobs").json()
        products = client.get("/api/v1/products").json()
        dashboard = client.get("/api/v1/dashboard").json()
    assert jobs[-1]["status"] == "completed"
    assert products[-1]["topic"] == "produtividade"
    assert dashboard["products"] >= 1

def test_factory_validates_topic() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/factory/produce", json={"topic": "x"})
    assert response.status_code == 422
