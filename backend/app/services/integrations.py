from ..core.config import get_settings, get_supabase_server_key


class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        supabase_server_key = get_supabase_server_key(settings)
        has_any_supabase_key = bool(settings.supabase_secret_key or settings.supabase_service_role_key)
        if supabase_server_key:
            supabase_message = "Chave de servidor válida detectada"
        elif has_any_supabase_key:
            supabase_message = "A chave configurada é publicável/anon ou não é service_role. Troque pela chave secreta de servidor."
        else:
            supabase_message = "Defina SUPABASE_URL e uma chave secreta de servidor."
        supabase_configured = bool(settings.supabase_url and supabase_server_key)
        redis_configured = bool(settings.redis_url and settings.redis_url.strip())
        return [
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY no Render."},
            {"name": "Supabase", "status": "connected" if supabase_configured else "not_configured", "message": supabase_message},
            {"name": "Redis", "status": "configured" if redis_configured else "not_configured", "message": "URL configurada" if redis_configured else "Defina REDIS_URL com a conexão privada do Render Key Value."},
            {"name": "Hotmart", "status": "connected" if settings.hotmart_client_id and settings.hotmart_client_secret else "not_configured", "message": "OAuth configurado; sincronização disponível" if settings.hotmart_client_id and settings.hotmart_client_secret else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Kiwify", "status": "connected" if settings.kiwify_webhook_token else "not_configured", "message": "Webhook protegido configurado; aguardando eventos de venda." if settings.kiwify_webhook_token else "Configure o token do webhook Kiwify no Render."},
            {"name": "Telegram", "status": "connected" if settings.telegram_bot_token and settings.telegram_chat_id else "not_configured", "message": "Notificações configuradas" if settings.telegram_bot_token and settings.telegram_chat_id else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
        ]


integration_service = IntegrationService()
