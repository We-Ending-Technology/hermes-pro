# Próxima etapa: integrações de marketplaces

## Objetivo

Adicionar suporte gradual a canais externos sem acoplar regras específicas ao núcleo do Hermes Pro. A primeira entrega deve operar em modo simulado e permanecer desabilitada por padrão.

## Ordem de execução

| Fase | Entrega | Critério de conclusão |
| --- | --- | --- |
| 1 | Contratos e configuração | Adapters tipados, catálogo de capacidades e flags por ambiente. |
| 2 | Sandbox/mock | Testes de publicação, consulta e tratamento de erros sem rede. |
| 3 | Primeiro marketplace | Um adapter real atrás de configuração explícita e credenciais do ambiente. |
| 4 | Observabilidade | Logs estruturados, correlation ID, métricas e retry com idempotência. |
| 5 | Expansão | Adapters adicionais reutilizando o mesmo contrato. |

## Contrato mínimo

Cada adapter deverá declarar `name`, `capabilities` e operações explícitas para publicação, consulta de status e sincronização. Operações destrutivas ou de alteração de catálogo deverão exigir idempotency keys. Erros de autenticação, limite de requisições e indisponibilidade deverão ser classificados separadamente.

## Segurança

Credenciais serão aceitas somente por variáveis protegidas do backend ou pelo secret manager do ambiente de deploy. Nenhuma credencial será colocada no frontend, no código-fonte, em fixtures ou em documentação. As integrações permanecerão desligadas quando a configuração estiver incompleta.

## Fora do primeiro incremento

Não implementar ainda checkout, pagamentos, sincronização de estoque em tempo real, publicação automática em produção ou múltiplos marketplaces simultaneamente. Essas capacidades dependem de contratos e testes de idempotência aprovados.
