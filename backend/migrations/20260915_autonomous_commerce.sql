create extension if not exists pgcrypto;

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

create table if not exists public.hermes_system_health (
  component text primary key,
  status text not null,
  message text,
  checked_at timestamptz not null default now()
);

create index if not exists hermes_opportunities_score_idx on public.hermes_opportunities(score desc);
create index if not exists hermes_opportunities_status_idx on public.hermes_opportunities(status);
create index if not exists hermes_expenses_occurred_idx on public.hermes_expenses(occurred_at desc);
create index if not exists hermes_events_occurred_idx on public.hermes_events(occurred_at desc);

alter table public.hermes_experiments enable row level security;
alter table public.hermes_system_health enable row level security;
