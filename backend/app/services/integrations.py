from ..core.config import get_settings

class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        return [
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY no Render."},
            {"name": "OpenAI fallback", "status": "connected" if settings.openai_api_key else "not_configured", "message": f"Fallback disponível ({settings.openai_model})" if settings.openai_api_key else "Defina OPENAI_API_KEY para fallback."},
            {"name": "Supabase", "status": "connected" if settings.supabase_url and settings.supabase_secret_key else "not_configured", "message": "Configuração presente" if settings.supabase_url and settings.supabase_secret_key else "Defina SUPABASE_URL e SUPABASE_SECRET_KEY."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Hotmart", "status": "connected" if settings.hotmart_client_id and settings.hotmart_client_secret else "not_configured", "message": "OAuth configurado; sincronização disponível" if settings.hotmart_client_id and settings.hotmart_client_secret else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Telegram", "status": "connected" if settings.telegram_bot_token and settings.telegram_chat_id else "not_configured", "message": "Notificações configuradas" if settings.telegram_bot_token and settings.telegram_chat_id else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
            {"name": "Freelancer", "status": "connected" if settings.freelancer_client_id and settings.freelancer_client_secret else "awaiting_credentials", "message": "OAuth pronto para ativação" if settings.freelancer_client_id and settings.freelancer_client_secret else "Aguardando Client ID/Secret do Freelancer."},
            {"name": "Upwork", "status": "connected" if settings.upwork_client_id and settings.upwork_client_secret else "awaiting_credentials", "message": "Integração preparada" if settings.upwork_client_id and settings.upwork_client_secret else "Aguardando credenciais do Upwork."},
            {"name": "Canva", "status": "connected" if settings.canva_client_id and settings.canva_client_secret else "awaiting_credentials", "message": "OAuth pronto para ativação" if settings.canva_client_id and settings.canva_client_secret else "Aguardando Client ID/Secret do Canva."},
            {"name": "Kill switch", "status": "active" if settings.hermes_kill_switch else "armed", "message": "Execução automática bloqueada" if settings.hermes_kill_switch else "Worker autorizado a executar jobs."},
        ]

integration_service = IntegrationService()
