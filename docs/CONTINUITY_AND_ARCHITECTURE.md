# Hermes Pro — documentação de continuidade

**Registro:** 05/11/2026  
**Finalidade:** manter a visão do produto, arquitetura, decisões, estado conhecido e plano de continuidade do Hermes Pro junto ao código.

> **Aviso de publicação:** este repositório é público. Este documento foi preparado para publicação segura: não contém senhas, tokens, chaves, URLs com credenciais, identificadores internos de infraestrutura ou dados pessoais. O inventário operacional detalhado permanece no dossiê privado do Notion. Não copie arquivos `.env` para este repositório.

## 1. O que é o Hermes

Hermes Pro é um sistema privado de automação e agentes pessoais. **Não é um SaaS**. Seu propósito é funcionar como uma central de comando capaz de coordenar agentes especializados, executar fluxos permitidos, acompanhar resultados, recuperar falhas e apresentar evidências reais ao proprietário.

### Princípios do produto

- Um agente Chefe coordena os agentes especialistas e mantém a visão geral do trabalho.
- O sistema deve avançar de ponta a ponta: descobrir, avaliar, executar quando autorizado, produzir artefatos, persistir resultados e recuperar falhas.
- Ações externas precisam respeitar as regras e APIs oficiais das plataformas.
- Resultados devem ter evidência verificável. Não simular clientes, vendas, tarefas ou integrações concluídas.
- Priorizar lucro líquido, custos, margem e sustentabilidade — não apenas faturamento.
- Manter aprovação humana, pausa, limites, alertas e mecanismo de parada de emergência (*kill switch*).
- Preservar dados, histórico e progresso. Não realizar gastos ou ações irreversíveis sem autorização explícita.
- Segredos ficam em gerenciadores de variáveis de ambiente dos provedores, nunca no Git.

## 2. Arquitetura conhecida

| Camada | Tecnologia / responsabilidade |
|---|---|
| Interface | React, Vite e PWA |
| API | Python e FastAPI |
| Agentes | Agentes especializados e orquestração pelo Chefe |
| IA | Gateway de provedores; Gemini identificado como primário no estado registrado |
| Processamento | Worker e fila para tarefas assíncronas |
| Persistência | PostgreSQL e Supabase |
| Armazenamento | Buckets para ebooks, capas e exportações |
| Hospedagem | Render e Vercel |
| Notificações | Telegram (integração ainda não validada ponta a ponta) |

A estrutura atual do repositório também descreve frontend, backend, gateway de IA, agentes, worker e migrações Supabase. Consulte o código e os testes para confirmar o comportamento implementado; a documentação não substitui validação executável.

## 3. Agentes e responsabilidades desejadas

- **Chefe:** recebe objetivos, divide tarefas, escolhe agentes, acompanha execução e consolida resultados.
- **Radar:** identifica oportunidades e sinais relevantes, filtra duplicatas e registra fontes.
- **Inteligência / Analista:** pesquisa, compara alternativas, estima viabilidade e apresenta evidências.
- **Executor técnico / Dev:** implementa alterações, executa testes e prepara mudanças rastreáveis.
- **Fábrica:** transforma ideias aprovadas em produtos e artefatos digitais.
- **Comercial:** prepara operações de distribuição e canais, sempre dentro das permissões oficiais.
- **Financeiro / Rentabilidade:** acompanha custos, receitas, margem e lucro líquido.
- **Auditor / Recuperação:** verifica evidências, idempotência, falhas, tentativas e recuperação.

Esta lista registra a organização desejada do sistema; não significa que todos os agentes e integrações estejam completos ou ativos.

## 4. Estado técnico registrado em 05/11/2026

### Identificado no projeto

- Repositório principal: [We-Ending-Technology/hermes-pro](https://github.com/We-Ending-Technology/hermes-pro).
- Branch de referência da fundação: `feat/hermes-foundation`.
- README descreve API FastAPI, interface React/Vite, gateway de IA, agentes, worker, migrações e testes.
- A documentação do projeto descreve orquestração, memória de agentes, fila Redis, execução de worker, retry/recuperação e scheduler.
- O modo autônomo é descrito como desativado até que as credenciais necessárias estejam configuradas.
- A API foi identificada anteriormente como versão 0.4.0.
- O projeto possui configurações de deploy declaradas em `render.yaml`.

### Integrações ainda não confirmadas como completas

- **Telegram:** estado anteriormente descrito como status-only; envio e recebimento ponta a ponta precisam ser testados.
- **Hotmart:** OAuth e webhook não estavam implementados ou confirmados.
- **Freelancer:** autorização de e-mail ainda pendente no registro anterior.
- **IA:** houve registros anteriores de erro 404 no Gemini e 503 no fallback. Validar modelos, permissões e fallback com testes reais.
- **Persistência:** é necessário comprovar que jobs, memória e resultados sobrevivem a reinicializações.

### Problemas registrados anteriormente

- Rotas de API esperadas retornaram 404 em uma inspeção anterior.
- Uma rota de jobs retornou 401.
- Houve configuração inválida de conexão de banco.
- A interface apresentou estado de API desconectada.
- O estado da aplicação após reinicialização ainda precisava de comprovação.

Esses pontos são histórico, não diagnóstico atual. Revalidar antes de corrigir ou alterar serviços.

## 5. Critérios mínimos de validação

O sistema não deve ser considerado operacional apenas porque a interface abre ou o deploy termina.

1. Health check e readiness devem responder corretamente.
2. Readiness deve executar uma consulta real ao PostgreSQL, como `SELECT 1`.
3. Confirmar que a API usa o banco de dados correto, sem expor a URL de conexão.
4. Criar um registro diagnóstico autenticado e ler o mesmo registro por identificador único.
5. Reiniciar o serviço e confirmar persistência e recuperação sem duplicar execução.
6. Validar upload e leitura reais de PNG, PDF e DOCX.
7. Testar worker, fila, retry, idempotência e auditoria.
8. Executar testes automatizados antes de qualquer deploy de correção.
9. Manter alterações em branch própria e abrir PR para revisão antes de integrar à branch principal.
10. Registrar evidências de execução, logs relevantes e resultado dos testes.

## 6. Segurança e proteção de dados

- Nunca versionar `.env`, tokens, senhas, API keys, chaves privadas, cookies ou URLs com credenciais.
- Não publicar dumps de banco, dados pessoais, dados de clientes ou arquivos de produção.
- Usar variáveis de ambiente e secrets managers dos provedores.
- Não abrir bancos de dados para todos os IPs. Preferir rede privada ou allowlist restrita e temporária.
- Não copiar credenciais antigas encontradas em repositórios legados. Se um segredo já foi publicado, considerar que está comprometido e fazer rotação no provedor correspondente.
- Revisar o conteúdo e o histórico antes de tornar qualquer cópia pública.
- Backups devem ser criptografados, ter checksum e passar por teste de restauração.

## 7. Repositórios legados e preservação

Foram identificados outros repositórios relacionados ao Hermes na conta pessoal, incluindo versões antigas, templates e protótipos. Eles não foram confirmados como cópias completas do projeto atual.

**Regra:** não apagar, sobrescrever ou tratar repositórios antigos como backup integral sem comparação de conteúdo, branches, commits e histórico. Um espelho Git verdadeiro deve preservar histórico e refs; copiar apenas arquivos Markdown ou o estado mais recente não é um espelho.

Foi observado anteriormente um arquivo `.env` versionado em um repositório legado público. Não replicar esse arquivo. Revisar e rotacionar credenciais que possam ter sido expostas.

## 8. Banco de dados e backup

No registro de 05/11/2026, havia um PostgreSQL Free no Render com prazo de expiração próximo. Naquele momento, **não havia backup completo nem restauração testada confirmados**.

Plano de preservação:

1. Exportar o banco com `pg_dump` por conexão autorizada e protegida por TLS, ou por job temporário na rede privada do provedor.
2. Não liberar o banco para `0.0.0.0/0`.
3. Armazenar o dump em destino durável e protegido.
4. Calcular checksum e verificar tamanho e integridade do arquivo.
5. Restaurar em uma instância separada.
6. Conferir schemas, tabelas, índices e registros essenciais.
7. Documentar data, versão do PostgreSQL, método e resultado do teste.

**Atenção:** um dump não testado não deve ser chamado de backup verificado. Este repositório não contém o dump.

## 9. Plano de trabalho priorizado

### Prioridade 0 — preservar dados

- [ ] Confirmar se o banco temporário ainda está disponível.
- [ ] Exportar PostgreSQL de forma segura.
- [ ] Testar restauração em banco separado.
- [ ] Fazer espelho Git real do repositório principal, preservando histórico, tags e branches relevantes.
- [ ] Guardar cópia independente e protegida do backup.

### Prioridade 1 — estabilizar a fundação

- [ ] Confirmar API, frontend e worker corretos.
- [ ] Corrigir readiness e conexão com PostgreSQL.
- [ ] Validar persistência após restart.
- [ ] Validar fila, retry, idempotência e auditoria.
- [ ] Corrigir testes e abrir PRs pequenos e rastreáveis.

### Prioridade 2 — integrações

- [ ] Validar gateway Gemini e fallback.
- [ ] Completar Telegram com envio real e tratamento de falhas.
- [ ] Implementar e validar OAuth/webhooks da Hotmart, se ainda fizerem parte do escopo.
- [ ] Retomar autorização do canal Freelancer quando solicitado.
- [ ] Manter credenciais fora do código.

### Prioridade 3 — autonomia controlada

- [ ] Ativar autonomia somente após testes e limites configurados.
- [ ] Implementar aprovação humana para ações externas sensíveis.
- [ ] Implementar pause, kill switch, orçamento e alertas.
- [ ] Fazer o Chefe consolidar relatórios com evidências e próximos passos.
- [ ] Monitorar falhas e recuperar tarefas sem duplicação.

## 10. Registro de mudanças

- **05/11/2026:** criado este documento de continuidade em branch própria. É documentação complementar; não representa migração do histórico Git, branches, banco de dados, secrets ou arquivos de produção.

## 11. Referências

- [Repositório principal](https://github.com/We-Ending-Technology/hermes-pro)
- [Render — Free services](https://render.com/docs/free)
- [Render — PostgreSQL backups](https://render.com/docs/postgresql-backups)
- [Render — PostgreSQL connections](https://render.com/docs/databases#connecting-to-a-render-postgres-database)
