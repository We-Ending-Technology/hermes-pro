from types import SimpleNamespace

from backend.app.services import integrations


def test_owner_social_profiles_are_registered_without_claiming_oauth_connection(monkeypatch):
    settings = SimpleNamespace(
        gemini_api_key=None,
        supabase_secret_key=None,
        supabase_service_role_key=None,
        supabase_url=None,
        redis_url="",
        shopify_store_domain=None,
        shopify_webhook_secret=None,
        hotmart_client_id=None,
        hotmart_client_secret=None,
        kiwify_api_client_id=None,
        kiwify_api_client_secret=None,
        kiwify_account_id=None,
        kiwify_webhook_token=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
    )
    monkeypatch.setattr(integrations, "get_settings", lambda: settings)
    monkeypatch.setattr(integrations, "get_supabase_server_key", lambda _: None)

    statuses = {item["name"]: item for item in integrations.IntegrationService().status()}

    assert statuses["YouTube"]["status"] == "profile_registered"
    assert "@ProjetoViral2wet" in statuses["YouTube"]["message"]
    assert statuses["Instagram"]["status"] == "profile_registered"
    assert "@projetoviral2wet" in statuses["Instagram"]["message"]
    assert statuses["TikTok"]["status"] == "profile_registered"
    assert statuses["Pinterest"]["status"] == "profile_registered"
    assert statuses["Facebook"]["status"] == "profile_registered"
    assert "URL/ID" in statuses["Facebook"]["message"]
    assert statuses["Metricool"]["status"] == "not_connected"
    assert statuses["Google Search Console"]["status"] == "not_configured"
    assert statuses["Google Analytics"]["status"] == "not_configured"
