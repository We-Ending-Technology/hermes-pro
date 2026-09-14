# Hermes Pro — handoff para Manus

## Objetivo
Levar o branch `feat/hermes-commercial-engine` até produção sem trocar a arquitetura aprovada.

## O que já foi implementado
- Command Center mobile-first em React/Vite.
- Navegação: Início, Produtos, Fábrica, Radar e Vendas.
- Views de Analytics e Agentes prontas no shell.
- API FastAPI para dashboard, produtos, jobs, radar, qualidade, vendas, analytics e integrações.
- Estados explícitos de indisponível/sem dados; nenhuma receita ou venda é simulada.
- Criação de produto assíncrona no contrato (`202 Accepted` + job).
- Idempotência básica por chave na sessão do processo.
- Adapter Gemini via API REST existente como único limite de IA.
- `render.yaml` com nomes das variáveis esperadas.
- PR de implementação aberto: #8, não fazer merge automático.

## O que ainda precisa ser feito
1. Persistir produtos, jobs e vendas no Supabase/Postgres; hoje os serviços comerciais são memória do processo.
2. Implementar worker real com Redis para consumir `product_generation` sem bloquear HTTP.
3. Completar pipeline Gemini: estrategista → escritor → revisor → geração de metadados; armazenar artefatos no Supabase Storage.
4. Gerar DOCX/PDF e capa usando os componentes/provedores já escolhidos no projeto; não adicionar novos provedores.
5. Implementar Hotmart OAuth/API e webhook com validação real. Só marcar publicado/vendido após confirmação da Hotmart.
6. Implementar Telegram com `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` e eventos de venda, publicação, falha e worker parado.
7. Conectar Sales/Analytics aos eventos persistidos da Hotmart e calcular receita/ticket apenas de dados reais.
8. Adicionar polling/backoff de job no Product Studio.
9. Adicionar testes de API, serviços, worker e um smoke test de frontend.
10. Executar `pytest`, `npm run build` e teste de navegador antes de qualquer merge/deploy.

## Variáveis do Render — API
Configurar no serviço `hermes-pro-api`:

```text
APP_ENV=production
AI_PROVIDER=gemini
GEMINI_API_KEY=<sua chave real>
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=<Postgres/Supabase real>
SUPABASE_URL=<URL do projeto Supabase>
SUPABASE_SECRET_KEY=<secret/service key real>
REDIS_URL=<URL Redis real>
CORS_ORIGINS=<URL pública do Vercel>,http://localhost:5173
HOTMART_CLIENT_ID=<credencial real>
HOTMART_CLIENT_SECRET=<credencial real>
HOTMART_WEBHOOK_TOKEN=<token/segredo usado para validar o webhook>
TELEGRAM_BOT_TOKEN=<token real do BotFather>
TELEGRAM_CHAT_ID=<chat id real>
```

## Variáveis do Render — Worker
No `hermes-pro-worker` usar pelo menos:

```text
APP_ENV=production
AI_PROVIDER=gemini
GEMINI_API_KEY=<mesma chave do backend>
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=<mesmo banco>
SUPABASE_URL=<mesmo projeto>
SUPABASE_SECRET_KEY=<mesma secret key>
REDIS_URL=<mesmo Redis>
```

## Variáveis da Vercel
No projeto frontend:

```text
VITE_API_URL=<URL HTTPS pública do serviço hermes-pro-api no Render>
```

Depois de alterar `VITE_API_URL`, criar novo deployment da Vercel, porque Vite incorpora essa variável no build.

## Ordem exata de configuração
1. Supabase: criar/confirmar banco e Storage e fornecer ao Manus as credenciais pelos secrets do ambiente, nunca pelo código.
2. Redis: confirmar URL acessível pelo Render.
3. Render API: preencher as variáveis e redeployar.
4. Abrir `https://<render-api>/health` e confirmar JSON com `status: ok`.
5. Vercel: preencher `VITE_API_URL` com a URL HTTPS do Render e redeployar.
6. Abrir o domínio da Vercel e confirmar que o painel carrega sem erro de API.
7. Hotmart: cadastrar o webhook apontando para o endpoint que o Manus implementar; usar o segredo de validação configurado no Render.
8. Telegram: adicionar o bot ao chat, enviar uma mensagem para o bot e obter o `chat_id`; configurar `TELEGRAM_CHAT_ID` no Render.
9. Fazer uma venda/teste controlado na Hotmart e confirmar que somente o evento confirmado alimenta Sales.

## Regras para Manus
- Não adicionar Eduzz, Kiwify ou outros marketplaces.
- Não adicionar novos provedores de IA.
- Não colocar chaves em GitHub, frontend ou arquivos públicos.
- Não exibir receita fictícia.
- Não chamar publicação de concluída antes da confirmação da Hotmart.
- Não fazer o HTTP esperar a geração completa do produto.
- Usar retries limitados e idempotência nos efeitos externos.
- Manter `/` e `/health` funcionando.
- Manter a interface mobile-first e sem scroll horizontal.
- Antes de afirmar que está pronto, executar e registrar os comandos de verificação.
