from ..core.config import get_settings

class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        supabase_key_configured = bool(settings.supabase_secret_key or settings.supabase_service_role_key)
        supabase_configured = bool(settings.supabase_url and supabase_key_configured)
        return [
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY no Render."},
            {"name": "Supabase", "status": "connected" if supabase_configured else "not_configured", "message": "Configuração presente" if supabase_configured else "Defina SUPABASE_URL e a chave secreta de servidor do Supabase."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Hotmart", "status": "connected" if settings.hotmart_client_id and settings.hotmart_client_secret else "not_configured", "message": "OAuth configurado; sincronização disponível" if settings.hotmart_client_id and settings.hotmart_client_secret else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Telegram", "status": "connected" if settings.telegram_bot_token and settings.telegram_chat_id else "not_configured", "message": "Notificações configuradas" if settings.telegram_bot_token and settings.telegram_chat_id else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
        ]

integration_service = IntegrationService()
