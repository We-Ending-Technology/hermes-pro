# Arquitetura técnica do Hermes Pro

## Fluxo atual

```text
Frontend React/Vite
      |
      v
FastAPI (/api/v1)
      |
      +--> Job store local de desenvolvimento
      +--> FactoryService
      |       +--> AI Gateway (stub ou Gemini configurado)
      |       +--> Quality Gate
      |       +--> ProductStore local
      |
      +--> Dashboard, jobs e produtos

Supabase REST, worker persistente e storage real permanecem como próximos incrementos.
```

## Serviços

| Serviço | Estado | Responsabilidade |
| --- | --- | --- |
| Frontend | Implementado | Painel inicial de dashboard, fábrica, produtos, jobs, logs e configurações. |
| API FastAPI | Implementado | Health check, agentes, produção, jobs, produtos e dashboard. |
| AI Gateway | Stub + Gemini preparado | Contrato comum e provider Gemini condicionado a variável de ambiente. |
| FactoryService | Implementado em modo local | Escrita, revisão, quality gate e documento Markdown. |
| Supabase | Migration + adapter preparado | Persistência real ainda depende de configuração e integração dos stores. |
| Worker | Entry point inicial | Worker persistente compartilhado ainda não implementado. |
| Render | Blueprint preparado | Deploy real depende de aplicação do Blueprint e variáveis protegidas. |

## Fluxo da fábrica

O endpoint `POST /api/v1/factory/produce` valida o tema, cria um job, executa o serviço da fábrica, salva o produto localmente e marca o job como concluído. O modo stub evita chamadas externas nos testes. Com `AI_PROVIDER=gemini`, o gateway chama o provider configurado no backend.

A publicação automática está desativada. O resultado atual é um documento Markdown armazenado na resposta e no store local; DOCX/PDF, storage persistente e catálogo de vendas são etapas posteriores.

## Segurança

A API key Gemini e a service role Supabase são lidas somente pelo backend. O frontend conhece apenas a URL pública da API. CORS é configurável por ambiente. Erros de produção retornam mensagem genérica ao cliente e não incluem credenciais.

## Próximos limites técnicos

Antes de produção, o job store e o product store devem ser substituídos por persistência Supabase. O worker deve reivindicar jobs com lock, retry limitado e estado durável. Autenticação e RLS devem existir antes de expor produtos e jobs de múltiplos usuários.
