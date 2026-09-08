create extension if not exists "pgcrypto";

create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null,
  status text not null default 'pending' check (status in ('pending','running','completed','failed','retrying')),
  input jsonb not null default '{}'::jsonb,
  output jsonb,
  error_message text,
  attempts integer not null default 0,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists agent_runs_status_idx on public.agent_runs(status);
create index if not exists agent_runs_created_at_idx on public.agent_runs(created_at desc);
