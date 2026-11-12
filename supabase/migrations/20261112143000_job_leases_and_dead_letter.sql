alter table public.hermes_jobs
  add column if not exists result jsonb not null default '{}'::jsonb,
  add column if not exists worker_id text,
  add column if not exists heartbeat_at timestamptz,
  add column if not exists max_attempts integer not null default 3;

create unique index if not exists hermes_jobs_idempotency_key_uq
  on public.hermes_jobs(idempotency_key)
  where idempotency_key is not null;

create index if not exists hermes_jobs_running_heartbeat_idx
  on public.hermes_jobs(status, heartbeat_at)
  where status = 'running';

create table if not exists public.hermes_jobs_dead_letter (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null,
  job_type text not null,
  payload jsonb not null default '{}'::jsonb,
  attempts integer not null default 0,
  error_message text,
  moved_at timestamptz not null default now(),
  resolved_at timestamptz
);

create unique index if not exists hermes_jobs_dead_letter_job_uq
  on public.hermes_jobs_dead_letter(job_id);

alter table public.hermes_jobs_dead_letter enable row level security;
revoke all on table public.hermes_jobs_dead_letter from anon, authenticated;
grant all on table public.hermes_jobs_dead_letter to service_role;
