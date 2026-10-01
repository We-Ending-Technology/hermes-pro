create table if not exists public.hermes_agent_memory (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  value jsonb not null default '{}'::jsonb,
  source text not null default 'agent',
  updated_at timestamptz not null default now()
);

create table if not exists public.hermes_agent_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid null,
  agent text not null,
  source text not null default 'manual',
  status text not null default 'pending',
  instruction text not null,
  output jsonb not null default '{}'::jsonb,
  requires_approval boolean not null default false,
  approved_at timestamptz null,
  error_message text null,
  started_at timestamptz null,
  completed_at timestamptz null,
  created_at timestamptz not null default now()
);

create index if not exists hermes_agent_runs_status_idx on public.hermes_agent_runs(status, created_at desc);
