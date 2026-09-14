from ..core.config import get_settings


class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        hotmart = bool(settings.hotmart_client_id and settings.hotmart_client_secret)
        telegram = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        return [
            {"name": "OpenAI", "status": "connected" if settings.openai_api_key else "not_configured", "message": "Chave configurada" if settings.openai_api_key else "Defina OPENAI_API_KEY (ou AI_API_KEY)."},
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY."},
            {"name": "Supabase", "status": "connected" if settings.supabase_url and settings.supabase_secret_key else "not_configured", "message": "Configuração presente" if settings.supabase_url and settings.supabase_secret_key else "Defina SUPABASE_URL e uma chave de serviço Supabase."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Hotmart", "status": "configured" if hotmart else "not_configured", "message": "Credenciais presentes; webhook/publicação ainda dependem da validação do fluxo real." if hotmart else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Telegram", "status": "connected" if telegram else "not_configured", "message": "Bot e chat configurados" if telegram else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
        ]


integration_service = IntegrationService()
