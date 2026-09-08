# Próximos passos

## Concluído

A fundação inicial contém frontend React/Vite, API FastAPI, gateway de IA stub, agentes, modelo de jobs, worker separado, Product Factory, Quality Gate, migration inicial do Supabase, Docker, Render, CI e documentação.

## Pendente

Ainda faltam autenticação, persistência real de jobs, fila externa, adapters reais de IA, Telegram, marketplaces, geração de ebooks e automação de produção.

## Arquivos principais criados

Consulte `git diff --stat` e as pastas `backend`, `frontend`, `docs`, `supabase` e `.github`.

## Testes

A suíte inicial passou com 3 testes. Os testes adicionais de domínio devem ser executados após sua inclusão.

## Próximo comando

```bash
source .venv/bin/activate && pytest
```
