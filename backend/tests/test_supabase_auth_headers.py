from backend.app.core.config import Settings
from backend.app.db.supabase import SupabaseREST


def test_new_supabase_secret_key_uses_apikey_without_bearer():
    settings = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="sb_secret_example",
    )

    client = SupabaseREST(settings)

    assert client.headers["apikey"] == "sb_secret_example"
    assert "Authorization" not in client.headers


def test_legacy_service_role_keeps_bearer_auth():
    settings = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="eyJlegacy",
    )

    client = SupabaseREST(settings)

    assert client.headers["apikey"] == "eyJlegacy"
    assert client.headers["Authorization"] == "Bearer eyJlegacy"


def test_service_role_key_takes_precedence_over_publishable_secret_alias():
    import base64
    import json

    payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    service_role = f"eyJheader.{payload}.signature"
    settings = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="sb_publishable_example",
        SUPABASE_SERVICE_ROLE_KEY=service_role,
    )

    client = SupabaseREST(settings)

    assert client.headers["apikey"] == service_role
    assert client.headers["Authorization"] == f"Bearer {service_role}"


def test_publishable_key_is_not_accepted_as_server_write_credential():
    settings = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SECRET_KEY="sb_publishable_example",
    )

    client = SupabaseREST(settings)

    assert client.secret_key is None
