# Credenciais — checklist rápido

| Serviço | Variáveis | Necessidade |
|---|---|---|
| OpenAI | OPENAI_API_KEY | Alta |
| Gemini | GEMINI_API_KEY | Alta |
| Supabase | SUPABASE_URL, SUPABASE_SECRET_KEY | Alta |
| Redis | REDIS_URL | Alta para fila compartilhada |
| Telegram | TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | Média |
| Freelancer | FREELANCER_CLIENT_ID, FREELANCER_CLIENT_SECRET, FREELANCER_ACCESS_TOKEN | Alta para aquisição via API |
| Canva | CANVA_CLIENT_ID, CANVA_CLIENT_SECRET | Média |
| Upwork | UPWORK_CLIENT_ID, UPWORK_CLIENT_SECRET, UPWORK_ACCESS_TOKEN | Futura |
| Pippit | PIPPIT_API_KEY | Opcional |
| Firecrawl | FIRECRAWL_API_KEY | Opcional |

**Não colocar secrets no GitHub.** Use Render Environment Variables.
