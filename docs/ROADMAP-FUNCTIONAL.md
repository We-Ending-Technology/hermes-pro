# Roadmap funcional do Hermes Pro

## Objetivo

Transformar a fundação atual em uma aplicação operacional, segura e observável. O trabalho deve avançar por incrementos pequenos, cada um com testes, migração reversível e Pull Request próprio. Nenhuma credencial deve entrar no código, no frontend, em fixtures ou na documentação.

## Estado atual

A fundação já possui frontend React/Vite, API FastAPI, gateway stub, agentes, worker separado, modelo inicial de jobs, Product Factory em modo stub, migration inicial do Supabase, Docker, Render, CI e contratos preliminares para marketplaces. A `main` contém os PRs #1 e #2.

## Ordem recomendada

| Fase | Entrega | Dependências | Critério de aceite |
| --- | --- | --- | --- |
| 1. Deploy mínimo | Frontend e API publicados, URL pública e health check | Configuração do Render e variáveis públicas | Frontend acessível; `GET /health` retorna `200`; logs sem secrets |
| 2. Dados reais | Supabase para banco, jobs, produtos, logs e storage | Fase 1; schema e políticas RLS | Migrations aplicadas; leitura e escrita cobertas por testes; dados isolados por usuário |
| 3. Identidade | Autenticação e proteção do painel administrativo | Supabase Auth e RLS | Usuário não autenticado não acessa rotas administrativas |
| 4. IA real | Gemini como provider principal, OpenAI como fallback | Fases 2 e 3; secrets no ambiente | Provider selecionado por configuração; fallback testado com mocks; custos e erros registrados |
| 5. Worker persistente | Execução de jobs sem navegador aberto | Supabase; Render worker; retry e idempotência | Jobs sobrevivem a reinício; estados nunca retrocedem; falhas ficam registradas |
| 6. Fábrica | Pipeline tema → job → escrita → revisão → nota → correção → documento → validação → produto | IA real; worker; storage | Um comando cria um produto de teste completo em ambiente não produtivo |
| 7. Dashboard | Produtos, jobs, erros, produção e worker | Dados reais, autenticação e eventos | Painel mostra estado do sistema sem dados mockados em produção |
| 8. Notificações | Telegram para conclusão, erro, publicação e venda | Identidade, eventos e secret backend | Eventos recebem notificações idempotentes; falha do Telegram não interrompe jobs |
| 9. Publicação e vendas | Adapters verificados por API e por capacidade real | Fábrica estável; contratos de cada canal | Cada operação suportada tem evidência documental e teste sandbox/mock |
| 10. Observabilidade | Monitoramento, alertas e recuperação segura | Worker e deploy estáveis | Worker parado, API indisponível, job travado e provider falho geram diagnóstico e alerta |
| 11. Evolução controlada | Diagnóstico → correção → testes → branch → PR → aprovação → deploy | CI, observabilidade e governança | Nenhuma mudança automática chega a `main` sem PR e aprovação humana |

## Critérios técnicos transversais

### Deploy

O frontend e a API devem ser publicados separadamente ou como serviços claramente delimitados. O endpoint `/health` deve verificar apenas a disponibilidade básica do processo; verificações de dependências devem ter endpoints ou métricas próprias para não mascarar falhas.

### Supabase

O schema deve separar usuários, jobs, produtos, artefatos, eventos e logs. Row Level Security (RLS) deve impedir acesso cruzado entre usuários. Storage deve usar buckets privados e URLs temporárias. Migrations devem ser versionadas e aplicadas pela CI ou por procedimento operacional documentado.

### IA

O gateway deve receber uma requisição normalizada e retornar provider, modelo, custo estimado quando disponível, latência, correlation ID e erro classificado. Fallback deve ocorrer apenas para falhas elegíveis, nunca para erros de validação ou conteúdo. Os testes devem usar adapters fake; chamadas reais só ocorrem quando os secrets estiverem configurados no ambiente.

### Fábrica e worker

Cada etapa deve ser idempotente e persistir seu resultado antes de liberar a próxima. O job deve possuir tentativas, timestamps, erro sanitizado, lock ou claim seguro e limite de retry. Um job travado não deve ser executado em duplicidade sem uma decisão explícita de recuperação.

### Publicação e vendas

Antes de implementar um adapter, deve ser verificado na documentação oficial se a plataforma oferece a operação necessária. O projeto não deve presumir que uma API de catálogo permite criação, publicação, pedido ou venda. Cada capability deve ter contrato separado, sandbox quando disponível, limites de rate limit e estratégia de idempotência.

### Monitoramento e evolução

Alertas devem ser acionáveis e conter correlation ID, job, etapa, provider e timestamp. A evolução automática deve criar apenas branches e Pull Requests. O merge em `main` e o deploy de produção permanecem ações aprovadas por uma pessoa.

## Fora de escopo imediato

Não ativar integrações reais, não inserir tokens, não implementar pagamentos, não publicar automaticamente em marketplaces, não gerar ebooks em produção e não permitir que agentes alterem `main` diretamente.

## Próximo incremento recomendado

O próximo PR deve implementar o deploy mínimo e o primeiro slice de Supabase: conexão configurável, migration de jobs/produtos/logs, health check operacional e testes de integração com banco local ou mock controlado. Depois disso, a autenticação deve ser adicionada antes de expor dados no dashboard.
