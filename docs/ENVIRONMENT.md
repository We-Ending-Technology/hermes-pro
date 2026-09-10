# Variáveis de ambiente

## Backend/API e worker

| Variável | Obrigatória agora | Local seguro | Observação |
| --- | --- | --- | --- |
| `APP_ENV` | Sim | Render/local `.env` | `development` ou `production`. |
| `CORS_ORIGINS` | Sim | Render/local `.env` | URLs permitidas do frontend, separadas por vírgula. |
| `AI_PROVIDER` | Não | Backend | Use `stub` para testes; `gemini` exige chave. |
| `GEMINI_API_KEY` | Só com Gemini | Secret do Render | Nunca no frontend ou Git. |
| `GEMINI_MODEL` | Não | Render/local `.env` | Padrão: `gemini-2.0-flash`. |
| `SUPABASE_URL` | Só com Supabase real | Secret/config do Render | URL pública do projeto. |
| `SUPABASE_SERVICE_ROLE_KEY` | Só com Supabase real | Secret do Render | Somente backend/worker. |
| `DATABASE_URL` | Futuro | Secret do Render | Ainda não é usada pelos stores atuais. |
| `REDIS_URL` | Futuro | Secret do Render | Necessária quando houver fila externa. |
| `MAX_JOB_RETRIES` | Não | Render/local `.env` | Limite de retries do worker futuro. |

## Frontend

| Variável | Local seguro | Observação |
| --- | --- | --- |
| `VITE_API_URL` | Configuração pública do serviço frontend | Pode ser pública; não coloque secrets em variáveis `VITE_*`. |

## Ainda não implementadas

Não configure como se estivessem operacionais: `KIWIFY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `POLLINATIONS_API_KEY` e `UPTIME_ROBOT_KEY`. Esses nomes só devem ser adicionados ao ambiente quando o adapter correspondente existir, estiver testado e tiver escopo aprovado.

## Regras

1. `.env` local não deve ser commitado.
2. Service roles e tokens ficam somente no Render ou secret manager.
3. GitHub Actions deve usar secrets apenas em jobs que realmente precisam deles.
4. O frontend nunca recebe `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` ou tokens de terceiros.
5. Se um segredo aparecer em logs, interrompa o deploy, rotacione-o e remova a exposição.
