from ..core.config import get_settings


class IntegrationService:
    def status(self) -> list[dict[str, str]]:
        settings = get_settings()
        hotmart = bool(settings.hotmart_client_id and settings.hotmart_client_secret)
        telegram = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        freelancer = bool(settings.freelancer_access_token)
        canva = bool(settings.canva_client_id and settings.canva_client_secret)
        upwork = bool(settings.upwork_access_token)
        pippit = bool(settings.pippit_api_key)
        firecrawl = bool(settings.firecrawl_api_key)
        return [
            {"name": "OpenAI", "status": "connected" if settings.openai_api_key else "not_configured", "message": "Chave configurada" if settings.openai_api_key else "Defina OPENAI_API_KEY."},
            {"name": "Gemini", "status": "connected" if settings.gemini_api_key else "not_configured", "message": "Chave configurada" if settings.gemini_api_key else "Defina GEMINI_API_KEY."},
            {"name": "Supabase", "status": "connected" if settings.supabase_url and settings.supabase_secret_key else "not_configured", "message": "Configuração presente" if settings.supabase_url and settings.supabase_secret_key else "Defina SUPABASE_URL e SUPABASE_SECRET_KEY."},
            {"name": "Redis", "status": "configured" if settings.redis_url else "not_configured", "message": "URL configurada" if settings.redis_url else "Defina REDIS_URL."},
            {"name": "Freelancer API", "status": "configured" if freelancer else "not_configured", "message": "Credencial presente; autenticação real será validada no preflight antes de qualquer envio." if freelancer else "Defina FREELANCER_CLIENT_ID, FREELANCER_CLIENT_SECRET e FREELANCER_ACCESS_TOKEN."},
            {"name": "Canva", "status": "configured" if canva else "not_configured", "message": "OAuth configurado; validar fluxo real antes de produção." if canva else "Defina CANVA_CLIENT_ID e CANVA_CLIENT_SECRET."},
            {"name": "Upwork", "status": "connected" if upwork else "not_configured", "message": "Token presente; validar escopos e permissões antes de automatizar." if upwork else "Defina as credenciais Upwork quando houver autorização/API disponível."},
            {"name": "Pippit", "status": "configured" if pippit else "not_configured", "message": "Chave presente." if pippit else "Opcional: defina PIPPIT_API_KEY."},
            {"name": "Firecrawl", "status": "configured" if firecrawl else "not_configured", "message": "Chave presente." if firecrawl else "Opcional: defina FIRECRAWL_API_KEY para coleta web robusta."},
            {"name": "Hotmart", "status": "configured" if hotmart else "not_configured", "message": "Credenciais presentes; publicação/webhooks ainda precisam de teste real." if hotmart else "Defina HOTMART_CLIENT_ID e HOTMART_CLIENT_SECRET."},
            {"name": "Telegram", "status": "connected" if telegram else "not_configured", "message": "Bot e chat configurados" if telegram else "Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."},
            {"name": "Radar", "status": "connected", "message": "Coleta, filtro, score, propostas e persistência disponíveis."},
        ]


integration_service = IntegrationService()
