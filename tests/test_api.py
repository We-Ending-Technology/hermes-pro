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


def test_postgres_driver_error_returns_503_without_exposing_details(monkeypatch) -> None:
    import psycopg
    import backend.app.main as main_module

    async def broken_select(*args, **kwargs):
        raise psycopg.ProgrammingError('missing "=" after "${{" in connection info string')

    monkeypatch.setattr(main_module.db, "select", broken_select)
    with TestClient(app) as client:
        response = client.get("/api/v1/products")

    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"
    assert "${{" not in response.text
    assert "connection info string" not in response.text



def test_freelancer_sync_accepts_scheduler_header(monkeypatch) -> None:
    import backend.app.main as main_module
    import backend.app.api_autonomy as autonomy_module

    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")

    async def fake_sync(**kwargs):
        return {"ok": True, "synced": 0}

    monkeypatch.setattr(autonomy_module, "sync_freelancer_contracts", fake_sync)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/autonomy/freelancer/sync",
            headers={"X-Hermes-Scheduler": "test-token"},
        )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_freelancer_sync_accepts_api_key_header(monkeypatch) -> None:
    import backend.app.main as main_module
    import backend.app.api_autonomy as autonomy_module

    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")

    async def fake_sync(**kwargs):
        return {"ok": True, "synced": 0}

    monkeypatch.setattr(autonomy_module, "sync_freelancer_contracts", fake_sync)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/autonomy/freelancer/sync",
            headers={"X-Hermes-API-Key": "test-token"},
        )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_freelancer_sync_rejects_missing_or_invalid_token(monkeypatch) -> None:
    import backend.app.main as main_module

    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")
    with TestClient(app) as client:
        missing = client.post("/api/v1/autonomy/freelancer/sync")
        invalid = client.post(
            "/api/v1/autonomy/freelancer/sync",
            headers={"X-Hermes-Scheduler": "wrong-token"},
        )
    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_freelancer_sync_reports_unconfigured_token(monkeypatch) -> None:
    import backend.app.main as main_module

    monkeypatch.setattr(main_module.settings, "hermes_api_token", None)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/autonomy/freelancer/sync",
            headers={"X-Hermes-Scheduler": "some-token"},
        )
    assert response.status_code == 503
