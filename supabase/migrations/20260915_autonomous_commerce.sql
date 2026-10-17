create table if not exists public.hermes_opportunities (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('product','service')),
  title text not null,
  description text,
  source text,
  source_url text,
  signals jsonb not null default '{}'::jsonb,
  score numeric(6,2),
  confidence numeric(4,2),
  status text not null default 'discovered',
  idempotency_key text unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_services (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid references public.hermes_opportunities(id) on delete set null,
  title text not null,
  briefing text,
  status text not null default 'candidate',
  difficulty numeric(6,2),
  estimated_hours numeric(8,2),
  estimated_value numeric(12,2),
  estimated_cost numeric(12,2),
  estimated_profit numeric(12,2),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_expenses (
  id uuid primary key default gen_random_uuid(),
  category text not null check (category in ('ai','infra','ads','other')),
  amount numeric(12,2) not null check (amount >= 0),
  currency text not null default 'BRL',
  description text,
  occurred_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.hermes_settings (
  id boolean primary key default true,
  kill_switch boolean not null default false,
  paused_domains jsonb not null default '[]'::jsonb,
  daily_ai_budget numeric(12,2),
  daily_ads_budget numeric(12,2),
  daily_total_budget numeric(12,2),
  human_approval_mode text not null default 'risk_based',
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  provider text,
  payload jsonb not null default '{}'::jsonb,
  idempotency_key text unique,
  occurred_at timestamptz not null default now()
);

create table if not exists public.hermes_agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent text not null,
  status text not null default 'pending',
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  error_message text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.hermes_opportunity_scores (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references public.hermes_opportunities(id) on delete cascade,
  score numeric(6,2) not null,
  confidence numeric(4,2) not null,
  dimensions jsonb not null default '{}'::jsonb,
  findings jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists hermes_opportunities_score_idx on public.hermes_opportunities(score desc, created_at desc);
create index if not exists hermes_opportunities_status_idx on public.hermes_opportunities(status, created_at desc);
create index if not exists hermes_services_status_idx on public.hermes_services(status, created_at desc);
create index if not exists hermes_expenses_occurred_idx on public.hermes_expenses(occurred_at desc);
create index if not exists hermes_agent_runs_created_idx on public.hermes_agent_runs(created_at desc);

alter table public.hermes_opportunities enable row level security;
alter table public.hermes_services enable row level security;
alter table public.hermes_expenses enable row level security;
alter table public.hermes_settings enable row level security;
alter table public.hermes_events enable row level security;
alter table public.hermes_agent_runs enable row level security;
alter table public.hermes_opportunity_scores enable row level security;

insert into public.hermes_settings(id) values (true) on conflict (id) do nothing;
