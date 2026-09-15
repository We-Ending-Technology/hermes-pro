create extension if not exists pgcrypto;

create table if not exists public.hermes_opportunities (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('product','service')),
  source text,
  source_url text,
  title text not null,
  evidence jsonb not null default '{}'::jsonb,
  score numeric(6,2),
  confidence numeric(6,2),
  status text not null default 'discovered',
  recommended_action text,
  idempotency_key text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_expenses (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  amount numeric(14,2) not null check (amount >= 0),
  currency text not null default 'BRL',
  source text,
  reference_id text,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.hermes_events (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id text,
  event_type text not null,
  actor text not null default 'system',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.hermes_experiments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  hypothesis text,
  status text not null default 'draft',
  variant_a jsonb not null default '{}'::jsonb,
  variant_b jsonb not null default '{}'::jsonb,
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_settings (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent text not null,
  status text not null,
  input jsonb not null default '{}'::jsonb,
  output jsonb not null default '{}'::jsonb,
  error_message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists public.hermes_system_health (
  component text primary key,
  status text not null,
  message text,
  checked_at timestamptz not null default now()
);

create index if not exists hermes_opportunities_score_idx on public.hermes_opportunities(score desc);
create index if not exists hermes_opportunities_status_idx on public.hermes_opportunities(status);
create index if not exists hermes_expenses_occurred_idx on public.hermes_expenses(occurred_at desc);
create index if not exists hermes_events_created_idx on public.hermes_events(created_at desc);

alter table public.hermes_opportunities enable row level security;
alter table public.hermes_expenses enable row level security;
alter table public.hermes_events enable row level security;
alter table public.hermes_experiments enable row level security;
alter table public.hermes_settings enable row level security;
alter table public.hermes_agent_runs enable row level security;
alter table public.hermes_system_health enable row level security;
