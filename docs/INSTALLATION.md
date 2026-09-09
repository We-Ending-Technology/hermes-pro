# Instalação e conexões do Hermes Pro

Este guia descreve como configurar o projeto com segurança. A fundação e o primeiro fluxo da fábrica já existem, mas **Gemini, Supabase, Render, Telegram, Kiwify e monitoramento externo ainda dependem de configuração e implementação específicas**. Não coloque chaves no Git, no frontend ou em mensagens de chat.

## 1. Pré-requisitos

Você precisa de uma conta no GitHub com acesso ao repositório, uma conta no Render para hospedagem, um projeto Supabase para banco e storage e uma credencial Gemini para o provider de IA. Telegram, Kiwify e Uptime Robot só devem ser configurados quando os respectivos adapters forem implementados e testados.

## 2. Configuração local

```bash
git clone https://github.com/We-Ending-Technology/hermes-pro.git
cd hermes-pro
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
pytest
cd frontend
npm install
npm run build
```

Para iniciar a API localmente:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Para iniciar o frontend:

```bash
cd frontend
npm run dev
```

O frontend usa `VITE_API_URL` quando fornecida. Sem essa variável, usa `http://localhost:8000`.

## 3. Supabase

Crie um projeto Supabase e guarde a URL e a chave de service role somente no ambiente do backend. A service role nunca deve ser usada no navegador. Aplique as migrations versionadas em `supabase/migrations/` usando o Supabase CLI ou o SQL Editor autenticado.

Variáveis necessárias no backend:

```text
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<configurar-fora-do-git>
```

O backend também aceita `SUPABASE_SECRET_KEY`, que é o nome usado pelo ambiente Render atual. Configure apenas uma das duas variáveis; ambas representam a chave privada do servidor.

Antes de habilitar dados de usuários, adicione autenticação e Row Level Security (RLS). A migration atual é a fundação de dados e ainda não substitui uma política completa de isolamento por usuário.

## 4. Gemini

Configure `AI_PROVIDER=gemini`, `GEMINI_MODEL` e `GEMINI_API_KEY` somente no backend. Em desenvolvimento e testes, mantenha `AI_PROVIDER=stub` para evitar chamadas e custos externos.

```text
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-2.0-flash
GEMINI_API_KEY=<configurar-fora-do-git>
```

O provider real possui timeout e registra provider/modelo na resposta. O fallback OpenAI ainda é uma extensão planejada; não configure fallback como se já estivesse operacional.

## 5. Render

O `render.yaml` descreve um frontend estático, uma API web e um worker. Crie os serviços a partir do Blueprint e preencha os valores protegidos no painel do Render. Configure `CORS_ORIGINS` com a URL pública exata do frontend e `VITE_API_URL` com a URL pública da API.

A URL pública só existe depois que o Blueprint for aplicado e os serviços forem publicados. O health check da API é:

```text
GET https://<api-publica>/health
```

## 6. Segredos e permissões

Use GitHub Actions apenas para testes e build até que um fluxo de deploy seja deliberadamente configurado. Não envie service roles, tokens de bots, chaves de IA ou tokens de marketplace para o GitHub. Prefira permissões mínimas e rotacione qualquer segredo que tenha sido exposto.

## 7. Estado das integrações ainda não entregues

Telegram, Kiwify, Pollinations.ai, Uptime Robot, autenticação completa, publicação automática, pagamentos e evolução autônoma não estão habilitados por este PR. O manual de produto descreve o objetivo futuro, mas não deve ser tratado como evidência de que essas APIs já foram conectadas.
