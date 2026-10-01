from ..core.config import get_settings

class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        return [
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY no Render."},
            {"name": "Supabase", "status": "connected" if settings.supabase_url and settings.supabase_secret_key else "not_configured", "message": "Configuração presente" if settings.supabase_url and settings.supabase_secret_key else "Defina SUPABASE_URL e SUPABASE_SECRET_KEY."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Hotmart", "status": "connected" if settings.hotmart_client_id and settings.hotmart_client_secret else "not_configured", "message": "OAuth configurado; sincronização disponível" if settings.hotmart_client_id and settings.hotmart_client_secret else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Telegram", "status": "connected" if settings.telegram_bot_token and settings.telegram_chat_id else "not_configured", "message": "Notificações configuradas" if settings.telegram_bot_token and settings.telegram_chat_id else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
            {"name": "Canva", "status": "connected" if settings.canva_client_id and settings.canva_client_secret else "not_configured", "message": "OAuth configurado" if settings.canva_client_id and settings.canva_client_secret else "Defina CANVA_CLIENT_ID e CANVA_CLIENT_SECRET."},
            {"name": "Freelancer.com", "status": "ready" if settings.freelancer_access_token and settings.freelancer_enabled else ("configured" if settings.freelancer_access_token else "not_configured"), "message": ("API + auto-apply habilitados" if settings.freelancer_access_token and settings.freelancer_enabled and settings.freelancer_auto_apply else ("API configurada; auto-apply desligado" if settings.freelancer_access_token else "Defina FREELANCER_ACCESS_TOKEN."))},
        ]

integration_service = IntegrationService()
