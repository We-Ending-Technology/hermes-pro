from app.core.config import Settings
from app.db.supabase import SupabaseREST
from app.services.storage import SupabaseStorage


def test_supabase_uses_edge_bridge_when_server_key_is_unavailable():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_bridge_secret="bridge-test-secret",
    )

    client = SupabaseREST(settings)

    assert client.base_url == "https://example.supabase.co/functions/v1/hermes-db-bridge"
    assert client.headers["apikey"] == "sb_publishable_test"
    assert client.headers["x-hermes-bridge-key"] == "bridge-test-secret"
    client._ensure_configured()


def test_supabase_prefers_direct_server_key_over_bridge():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJyb2xlIjoic2VydmljZV9yb2xlIn0.signature"
        ),
        supabase_publishable_key="sb_publishable_test",
        supabase_bridge_secret="bridge-test-secret",
    )

    client = SupabaseREST(settings)

    assert client.base_url == "https://example.supabase.co/rest/v1"
    assert client.headers["apikey"].startswith("eyJ")
    assert client.headers["Authorization"].startswith("Bearer eyJ")
    assert "x-hermes-bridge-key" not in client.headers


def test_new_supabase_secret_key_is_not_sent_as_bearer_jwt():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    client = SupabaseREST(settings)

    assert client.base_url == "https://example.supabase.co/rest/v1"
    assert client.headers["apikey"] == "sb_secret_test"
    assert "Authorization" not in client.headers



def test_storage_uses_edge_bridge_when_server_key_is_unavailable():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_bridge_secret="bridge-test-secret",
    )

    storage = SupabaseStorage(settings, bucket="ebooks")

    assert storage.storage_base == "https://example.supabase.co/functions/v1/hermes-db-bridge/storage"
    assert storage._headers() == {
        "apikey": "sb_publishable_test",
        "x-hermes-bridge-key": "bridge-test-secret",
    }
    storage._ensure_configured()


def test_storage_sends_new_secret_key_without_bearer_header():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    storage = SupabaseStorage(settings, bucket="ebooks")

    assert storage.storage_base == "https://example.supabase.co/storage/v1"
    assert storage._headers() == {"apikey": "sb_secret_test"}
