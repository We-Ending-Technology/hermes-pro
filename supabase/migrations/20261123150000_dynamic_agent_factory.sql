-- Dynamic, owner-controlled agent registry and independent execution history.
-- The private backend uses the service-role/bridge path; browser roles get no table access.

create table if not exists public.hermes_agents (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  role text not null,
  instructions text not null,
  capabilities jsonb not null default '["analysis"]'::jsonb,
  permissions jsonb not null default '["ai.complete","memory.read","memory.write"]'::jsonb,
  tool_allowlist jsonb not null default '[]'::jsonb,
  status text not null default 'draft'
    check (status in ('draft', 'active', 'disabled')),
  approval_required boolean not null default true,
  approved_at timestamptz null,
  approved_by text null,
  approval_note text null,
  version integer not null default 1 check (version > 0),
  created_by text not null default 'hermes_private_api',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint hermes_agents_slug_format check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  constraint hermes_agents_capabilities_allowlist check (
    jsonb_typeof(capabilities) = 'array'
    and capabilities @> '["analysis"]'::jsonb
    and capabilities <@ '["analysis"]'::jsonb
  ),
  constraint hermes_agents_permissions_allowlist check (
    jsonb_typeof(permissions) = 'array'
    and permissions @> '["ai.complete"]'::jsonb
    and permissions <@ '["ai.complete","memory.read","memory.write"]'::jsonb
  ),
  constraint hermes_agents_no_tools check (tool_allowlist = '[]'::jsonb),
  constraint hermes_agents_activation_requires_approval check (
    status <> 'active'
    or (approval_required = false and approved_at is not null and approved_by is not null)
  )
);

create index if not exists hermes_agents_status_idx
  on public.hermes_agents(status, updated_at desc);

create table if not exists public.hermes_agent_execution_runs (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null,
  agent_id uuid not null references public.hermes_agents(id) on delete restrict,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  provider text null,
  model text null,
  error_message text null,
  started_at timestamptz not null default now(),
  completed_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists hermes_agent_execution_runs_agent_idx
  on public.hermes_agent_execution_runs(agent_id, created_at desc);
create index if not exists hermes_agent_execution_runs_correlation_idx
  on public.hermes_agent_execution_runs(correlation_id, created_at);

alter table public.hermes_agents enable row level security;
alter table public.hermes_agent_execution_runs enable row level security;

revoke all privileges on table public.hermes_agents from anon, authenticated;
revoke all privileges on table public.hermes_agent_execution_runs from anon, authenticated;
grant all privileges on table public.hermes_agents to service_role;
grant all privileges on table public.hermes_agent_execution_runs to service_role;

-- The existing code-defined specialists are seeded as approved system agents.
-- Newly created agents always start as draft and require explicit owner approval.
insert into public.hermes_agents
  (slug, name, role, instructions, capabilities, permissions, status,
   approval_required, approved_at, approved_by, approval_note)
values
  ('hermes-chefe', 'Hermes Chefe', 'orchestrator',
   'Coordene especialistas independentes, compare resultados, identifique divergências e entregue uma síntese verificável. Nunca execute ações externas sem autorização.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Agente-base já existente no código do Hermes'),
  ('hermes-radar', 'Hermes Radar', 'market_research',
   'Analise sinais, oportunidades, riscos e lacunas de informação. Não invente dados de mercado, fontes ou validações.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-factory', 'Hermes Factory', 'product_creation',
   'Transforme tarefas aprovadas em soluções ou produtos digitais executáveis. Defina entregáveis, critérios de qualidade e dependências reais.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-dev', 'Hermes Dev', 'engineering',
   'Analise arquitetura, integrações, falhas técnicas e testes. Não afirme que executou alterações que não foram realizadas.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-analyst', 'Hermes Analyst', 'data_analysis',
   'Avalie custos, riscos, retorno, métricas e viabilidade usando dados documentados. Marque hipóteses e lacunas.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-designer', 'Hermes Designer', 'editorial_design',
   'Defina estrutura editorial, hierarquia visual, legibilidade, identidade da capa e ilustrações.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-capas', 'Hermes Capas', 'ebook_cover_generation',
   'Especifique capas editoriais e critérios de validação. Não declare arquivos gerados sem evidência binária.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-auditor', 'Hermes Auditor', 'quality_security_audit',
   'Audite qualidade, segurança, integridade, rastreabilidade e conformidade. Bloqueie publicação quando faltar evidência.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-executor', 'Hermes Executor', 'task_execution_planning',
   'Converta decisões aprovadas em tarefas persistentes, idempotentes e verificáveis. Não publique, gaste ou execute ações irreversíveis sem aprovação.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-comercial', 'Hermes Comercial', 'commercial_operations',
   'Prepare propostas de oferta, descrição, público, preço e checkout. Nunca invente checkout, preço aprovado ou publicação.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-rentabilidade', 'Hermes Rentabilidade', 'profitability',
   'Calcule receita líquida, taxas, comissões, custos e margem com valores documentados. Se faltar dado, retorne desconhecido.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes'),
  ('hermes-sentinel', 'Hermes Sentinel', 'monitoring_recovery',
   'Analise health checks, heartbeats, incidentes e tarefas órfãs. Separe falhas detectadas, ações executadas e resultados confirmados.',
   '["analysis"]'::jsonb, '["ai.complete","memory.read","memory.write"]'::jsonb,
   'active', false, now(), 'system_seed', 'Especialista-base já existente no código do Hermes')
on conflict (slug) do nothing;
