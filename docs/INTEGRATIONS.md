# Hermes Pro — Integrações e credenciais

O Hermes foi preparado para funcionar com credenciais injetadas por ambiente. **Nunca coloque tokens, client secrets ou chaves dentro do GitHub.**

## Obrigatórias para o núcleo
- `OPENAI_API_KEY` — IA/fallback
- `GEMINI_API_KEY` — geração primária, se escolhido
- `SUPABASE_URL` + `SUPABASE_SECRET_KEY` — persistência
- `REDIS_URL` — fila compartilhada, quando usada
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — alertas

## Aquisição de freelas
### Freelancer
Variáveis:
- `FREELANCER_CLIENT_ID`
- `FREELANCER_CLIENT_SECRET`
- `FREELANCER_ACCESS_TOKEN`

A documentação oficial do Freelancer informa que existe API, OAuth e sandbox. Primeiro configure o cliente OAuth e obtenha uma autorização/token válidos; depois cole somente os valores no Render.

### Upwork
O Hermes já possui espaço para:
- `UPWORK_CLIENT_ID`
- `UPWORK_CLIENT_SECRET`
- `UPWORK_ACCESS_TOKEN`

Não habilite envio automático até que a API/escopos estejam efetivamente autorizados para a conta.

## Produção de criativos
### Canva
- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`

### Pippit
- `PIPPIT_API_KEY` (opcional)

## Coleta web
### Firecrawl
- `FIRECRAWL_API_KEY` (opcional)

Se não houver Firecrawl, o Radar usa as URLs públicas configuradas em `RADAR_SOURCE_URLS`.

## Controle de risco
- `RADAR_MIN_SCORE=65`
- `AUTO_APPLY_ENABLED=false`
- `MAX_APPLICATIONS_PER_DAY=5`

O padrão é seguro: o Hermes pode encontrar, pontuar e preparar propostas, mas não envia candidatura automaticamente sem uma integração/autorização válida e explicitamente habilitada.

## Checklist de ativação
1. Criar/obter a credencial no provedor.
2. Colar no Render Environment.
3. Fazer redeploy.
4. Abrir `/api/v1/integrations`.
5. Confirmar o status da integração.
6. Só então habilitar a etapa seguinte.

Nunca compartilhe uma chave secreta no chat.
