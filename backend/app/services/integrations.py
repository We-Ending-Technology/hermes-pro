from ..core.config import get_settings

class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        return [
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY no Render/Vercel."},
            {"name": "Supabase", "status": "connected" if settings.supabase_url and settings.supabase_secret_key else "not_configured", "message": "Configuração presente" if settings.supabase_url and settings.supabase_secret_key else "Defina SUPABASE_URL e SUPABASE_SECRET_KEY."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Hotmart", "status": "not_configured", "message": "Conector comercial precisa das credenciais/webhook reais antes de publicar."},
            {"name": "Telegram", "status": "not_configured", "message": "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID para notificações."},
        ]

integration_service = IntegrationService()
