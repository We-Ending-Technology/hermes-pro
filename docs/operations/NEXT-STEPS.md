# Próximos passos

## Concluído nesta branch

Foi criada a branch `feat/functional-factory-slice` a partir da `main` em `7e4c8e6`. A API agora possui endpoints funcionais para iniciar produção, listar jobs, listar produtos e consultar o dashboard. O fluxo de fábrica usa o gateway stub local, executa escrita, revisão, quality gate, documento Markdown e salva o produto em store local de desenvolvimento. O frontend possui navegação funcional para Dashboard, Fábrica, Produtos, Jobs, Logs e Configurações. O Render e `.env.example` foram atualizados com variáveis explícitas para Supabase e Gemini.

## Pendente antes de produção

Supabase ainda precisa de URL, service role key e migrations aplicadas em um projeto real. Gemini ainda precisa de `GEMINI_API_KEY` configurada no servidor. O worker persistente ainda precisa mover o processamento para uma fila compartilhada e sobreviver a reinícios. Autenticação, storage real, logs persistentes, monitoramento e deploy público ainda não foram ativados. O produto não é publicado automaticamente.

## Validações esperadas

```bash
source .venv/bin/activate && pytest
cd frontend && npm run build
```

## Próximo comando

Depois de configurar os secrets somente no ambiente do Render/Supabase, implementar o repositório persistente de jobs e executar o worker contra a mesma fonte de dados usada pela API. Não adicionar secrets ao Git.

## Documentação de configuração adicionada

Foram adicionados `docs/INSTALLATION.md`, `docs/ARCHITECTURE.md` e `docs/ENVIRONMENT.md` com instruções seguras para GitHub, Render, Supabase e Gemini. O manual de produto não foi tratado como evidência de integrações existentes: Kiwify, Telegram, Pollinations.ai, Uptime Robot, autenticação completa e evolução autônoma continuam pendentes.
