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
