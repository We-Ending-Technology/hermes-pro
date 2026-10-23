from fastapi.testclient import TestClient

from backend.app.main import app


class FakeDiagnosticsDB:
    def __init__(self):
        self.rows = {}
        self.keys = {}

    async def identity(self):
        return {"database_name": "hermes_test_db", "schema_name": "public"}

    async def select(self, table, *, params=None):
        params = params or {}
        if "idempotency_key" in params:
            key = params["idempotency_key"].removeprefix("eq.")
            row_id = self.keys.get(key)
            return [self.rows[row_id]] if row_id else []
        if "id" in params:
            row_id = params["id"].removeprefix("eq.")
            return [self.rows[row_id]] if row_id in self.rows else []
        return list(self.rows.values())

    async def insert(self, table, values):
        row = dict(values)
        self.rows[row["id"]] = row
        self.keys[row["idempotency_key"]] = row["id"]
        return row

    async def claim_persistence_test_execution(self, test_id):
        row = self.rows.get(test_id)
        if row is None:
            from backend.app.db.postgres import DatabaseError
            raise DatabaseError("Teste de persistência não encontrado.")
        if row["status"] == "pending":
            row["status"] = "executed"
            row["execution_count"] = 1
            return dict(row), True
        return dict(row), False


def setup_test(monkeypatch):
    import backend.app.main as main_module
    import backend.app.api_diagnostics as diagnostics_module

    monkeypatch.setattr(main_module.settings, "hermes_api_token", "test-token")
    fake_db = FakeDiagnosticsDB()
    monkeypatch.setattr(diagnostics_module, "db", fake_db)
    return fake_db


def test_persistence_test_requires_authentication(monkeypatch):
    setup_test(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/diagnostics/persistence-test",
            headers={"Idempotency-Key": "auth-test"},
            json={},
        )
    assert response.status_code == 401


def test_create_read_and_execute_is_idempotent(monkeypatch):
    setup_test(monkeypatch)
    headers = {"X-Hermes-API-Key": "test-token", "Idempotency-Key": "unique-test-001"}
    with TestClient(app) as client:
        created = client.post("/api/v1/diagnostics/persistence-test", headers=headers, json={})
        assert created.status_code == 201
        body = created.json()
        test_id = body["test"]["id"]
        assert body["created"] is True
        assert body["test"]["execution_count"] == 0

        duplicate = client.post("/api/v1/diagnostics/persistence-test", headers=headers, json={})
        assert duplicate.status_code == 200
        assert duplicate.json()["created"] is False
        assert duplicate.json()["test"]["id"] == test_id

        read = client.get(
            f"/api/v1/diagnostics/persistence-test/{test_id}",
            headers={"X-Hermes-API-Key": "test-token"},
        )
        assert read.status_code == 200
        assert read.json()["test"]["id"] == test_id

        first = client.post(
            f"/api/v1/diagnostics/persistence-test/{test_id}/execute",
            headers={"X-Hermes-API-Key": "test-token"},
        )
        second = client.post(
            f"/api/v1/diagnostics/persistence-test/{test_id}/execute",
            headers={"X-Hermes-API-Key": "test-token"},
        )
        assert first.status_code == 200
        assert first.json()["executed_now"] is True
        assert second.status_code == 200
        assert second.json()["already_executed"] is True
        assert second.json()["test"]["execution_count"] == 1


def test_persistence_test_not_found(monkeypatch):
    setup_test(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/diagnostics/persistence-test/not-a-real-id",
            headers={"X-Hermes-API-Key": "test-token"},
        )
    assert response.status_code == 404


def test_database_identity_is_authenticated_and_safe(monkeypatch):
    setup_test(monkeypatch)
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/diagnostics/database-identity")
        authorized = client.get("/api/v1/diagnostics/database-identity", headers={"X-Hermes-API-Key": "test-token"})
    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"database_name": "hermes_test_db", "schema_name": "public"}
