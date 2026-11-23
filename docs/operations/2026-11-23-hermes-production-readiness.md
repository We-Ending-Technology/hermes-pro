# Hermes Pro — plano mestre de conclusão e autonomia

Data: 2026-11-23
Status: plano de engenharia baseado na auditoria real; não representa funcionalidades já implantadas.

## Objetivo
Concluir o Hermes Pro privado como plataforma de operação autônoma e auditável para pesquisa, criação de produtos, conteúdo, distribuição, vendas e evolução técnica. Preservar os serviços atuais, priorizar custo zero, não inventar resultados e não executar ações financeiras ou irreversíveis sem autorização explícita.

## Estado verificado nesta auditoria

### Infraestrutura
- Repositório: `We-Ending-Technology/hermes-pro`; branch padrão: `feat/hermes-foundation`.
- API Render `hermes-pro-api-commercial` implantada em `feat/hermes-foundation`, plano free.
- Frontend Render `hermes-pro-command-center` implantado em `feat/hermes-autonomous-hardening`.
- Site público Projeto Viral 2 Wet em `feat/projeto-viral-public-site`; PR #136 aberta.
- Supabase `hermes-commerce-v2` ativo e saudável.
- Endpoints públicos verificados: `/health` = ok; `/ready` = ready; Supabase, Redis e provedor primário de IA configurados.
- Worker heartbeat recente: status ok, filas de produto e agente vazias.
- O plano gratuito do Render não garante execução ininterrupta; serviços podem dormir por inatividade.

### Dados observados no Supabase
- hermes_products: 54
- hermes_jobs: 105 (27 completed, 23 failed, 55 paused na consulta)
- hermes_offers: 5 (todas draft)
- hermes_sales_events: 0
- hermes_agent_runs: 24 (7 completed, 17 failed)
- hermes_agent_memory: 1
- hermes_incidents: 9 (todos resolved na consulta)
- hermes_market_signals: 623

### Falhas predominantes observadas
- Erros de IA Gemini HTTP 429 e 503.
- Erros HTTP 404 por identificadores de modelo antigos.
- O fallback de IA está configurado como none no runtime reportado.
- 53 jobs pausados com mensagem de espera por limite diário aprovado de gastos de IA; não remover essa pausa automaticamente.
- Os dados não comprovam vendas: não há eventos de venda registrados.

### Divergência de branches e PRs
- API usa `feat/hermes-foundation`.
- Frontend usa `feat/hermes-autonomous-hardening`.
- PR #13 (hardening comercial) continua aberta, destino `feat/hermes-foundation`; precisa de CI/revisão de compatibilidade antes de merge.
- PR #136 (site público) continua aberta; não mesclar em lote.
- Há outras PRs antigas e branches com bases divergentes. Fazer inventário, comparar arquivos e escolher uma linha de integração; nunca merge em massa.

### Limitação da implementação atual de agentes
- O runtime registra especialistas fixos em código.
- `AgentRegistry` oferece apenas register/get/names; não há cadastro dinâmico persistente.
- `run_chief` solicita perspectivas de vários especialistas em uma única chamada ao provedor; isso não comprova subagentes independentes com execução/ferramentas próprias.
- O histórico de execuções e a memória existem, mas o volume de memória é baixo e a taxa de falha das execuções consultadas é alta.
- Portanto, a Fábrica de Agentes dinâmica ainda não está pronta.

## Arquitetura-alvo

1. Control Plane: Hermes Chefe, prioridades, políticas, aprovações, orçamento, kill switch.
2. Agent Registry: definições versionadas, capacidades, ferramentas permitidas, limites e estado.
3. Orchestration Plane: tarefas persistentes, subtarefas, dependências, filas, leases, retries limitados e idempotência.
4. Execution Plane: agentes especializados executados isoladamente, cada um com ferramentas explicitamente autorizadas.
5. Memory Plane: memória factual com origem, data, confiança, validade e mecanismo de correção.
6. Engineering Plane: análise de repositório, branch/worktree isolado, testes, revisão, PR e deploy staged/rollback.
7. Commercial Plane: pesquisa, produtos, ativos, ofertas, checkout, entrega, eventos reais, taxas, margem e reembolso.
8. Observability Plane: health/readiness, heartbeat, traces, logs, incidentes, custos, alertas e evidências.

## Plano de execução e gates

### Gate 0 — estabilizar e reconciliar ambientes
- Identificar o commit implantado em cada serviço e documentar a matriz branch/commit/build.
- Revisar PR #13, PR #136 e demais PRs relevantes; comparar diferenças e CI.
- Garantir que API e frontend apontem para contratos compatíveis.
- Executar testes completos de backend e build/testes do frontend em CI.
- Fazer backup verificável do banco e preservar branches/artefatos antes de qualquer merge.
- Critério: uma linha de release definida, API/UI compatíveis e CI verde.

### Gate 1 — confiabilidade do núcleo
- Reproduzir e classificar falhas de jobs e agent runs.
- Implementar fallback real de IA somente com credencial disponível e teste de saúde; não assumir que variável configurada significa provedor funcional.
- Limitar retries com backoff/jitter, circuit breaker e orçamento por provedor.
- Garantir idempotência, leases e recuperação sem duplicação.
- Validar persistência de resultados e erros.
- Critério: tarefa diagnóstica real conclui; falha simulada recupera sem duplicação; readiness reporta dependências reais.

### Gate 2 — Fábrica de Agentes
- Criar catálogo persistente de definições versionadas de agentes.
- Campos mínimos: name, slug, role, instructions, allowed_tools, autonomy_level, status, version, created_by, timestamps.
- Criar endpoints autenticados para listar, criar, versionar, ativar, pausar e arquivar agentes.
- Validar nome/slug único, tamanho de instruções, allowlist de ferramentas, limites de concorrência e profundidade máxima de delegação.
- Agente novo começa em draft; ativação depende de teste de contrato e avaliação.
- Não permitir código arbitrário, acesso a secrets, autoelevação de permissões ou criação recursiva ilimitada.
- Critério: Chefe cria um agente draft, persiste, executa tarefa autorizada em sandbox, registra evidências, avalia e ativa somente se aprovado.

### Gate 3 — orquestração multiagente real
- Cada execução tem run_id, parent_run_id, agent_definition_version, status, input/output, custo estimado/real, timestamps e evidence refs.
- Delegação cria subtarefas persistentes e limites de profundidade/fan-out.
- Fila com idempotency key, leases, retries limitados, dead-letter e cancelamento.
- Ferramentas por capacidade e menor privilégio.
- Critério: pai cria dois filhos independentes, ambos concluem, pai consolida resultados e auditor consegue rastrear a cadeia.

### Gate 4 — Engenharia autônoma
- Agente de engenharia apenas leitura no início; depois escrita somente em branch isolada.
- Criar plano, testes primeiro, alteração mínima, CI, revisão de código e PR.
- Nunca permitir que agente faça merge/deploy direto em produção.
- Deploy gradual com smoke test e rollback documentado.
- Critério: agente propõe e implementa uma correção não crítica em branch; CI valida; PR contém evidências; produção não muda sem gate autorizado.

### Gate 5 — operação comercial e mídia
- Validar entrega do arquivo do primeiro produto Kiwify sem compra real nem cobrança.
- Corrigir e validar ofertas em draft; manter aprovação humana antes de ativar preço/publicação.
- Fábrica de vídeos: roteiro, direitos, assets, render FFmpeg fora da API de baixa memória, armazenamento, legendas, revisão e publicação por APIs oficiais.
- YouTube principal para conteúdo geral; conteúdo infantil em canal separado com classificação e revisão próprias.
- Conectar Search Console/GA4 na conta correta, redes sociais e Metricool após login/OAuth oficial.
- Critério: um produto passa por compra de teste no sandbox quando disponível ou validação documental sem transação; um vídeo de teste é gerado, auditado e salvo; publicação social ocorre apenas após autorização.

### Gate 6 — operação contínua
- Monitoramento externo de uptime, fila, heartbeat, IA, storage, webhooks e eventos comerciais.
- Alertas e recuperação segura; escalonamento humano para falhas não recuperáveis.
- Agendamentos e autonomia limitados por orçamento e quotas.
- Documentar que Render Free não garante 24/7; escolher executor gratuito confiável ou solicitar orçamento antes de mudar de plano.
- Critério: simulação de falha gera incidente, diagnóstico, ação permitida, validação e alerta; nenhum custo excede orçamento.

## Segurança e conformidade
- Não guardar tokens ou credenciais em prompts, logs, Git ou memória de agente.
- OAuth, 2FA, CAPTCHA, identidade, termos, revisão de app e ações financeiras exigem ação humana.
- Sem spam, scraping proibido, conteúdo enganoso, plágio, compra de tráfego ou publicação infantil sem revisão.
- Kill switch global e por canal; allowlist de ferramentas; rate limits; orçamento diário; audit trail imutável.
- Dados financeiros devem distinguir previsto, pendente, aprovado, reembolsado e conciliado.

## Critérios de conclusão do projeto
O projeto só pode ser considerado pronto quando:
- CI backend/frontend verde na release escolhida.
- API e painel compatíveis e protegidos.
- Backup restaurável verificado.
- Worker, fila, scheduler, retries e recuperação testados.
- Agente dinâmico criado e executado ponta a ponta com evidências.
- Engenharia autônoma limitada a PRs e CI, sem auto-deploy descontrolado.
- Produto digital com checkout e entrega verificados.
- Conteúdo produzido e armazenado com direitos e qualidade auditados.
- Webhooks e vendas reconciliados com eventos reais.
- Monitoramento e alertas testados.
- Nenhuma falha crítica aberta; limitações e riscos restantes documentados.

## Decisões operacionais fixas
- Prioridade: reaproveitar o projeto existente e manter custo zero.
- Não habilitar serviços pagos, recargas, anúncios ou compras sem autorização explícita.
- Não reativar o Radar diário de freelancers.
- Não apagar jobs pausados, falhas históricas, branches ou PRs sem análise.
- Não declarar receita, publicação, integração ou correção sem evidência independente.
- Não modificar produção enquanto o branch/commit implantado e o backup não estiverem identificados.
