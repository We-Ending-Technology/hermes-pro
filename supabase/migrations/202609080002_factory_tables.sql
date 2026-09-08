create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null,
  status text not null default 'pending' check (status in ('pending','running','completed','failed','retrying')),
  payload jsonb not null default '{}'::jsonb,
  error_message text,
  attempts integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  topic text not null,
  quality_score integer check (quality_score between 0 and 100),
  document_path text,
  status text not null default 'draft',
  created_at timestamptz not null default now()
);

create table if not exists public.job_executions (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs(id) on delete cascade,
  stage text not null,
  provider text,
  status text not null,
  input jsonb,
  output jsonb,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.system_logs (
  id uuid primary key default gen_random_uuid(),
  level text not null,
  event text not null,
  job_id uuid references public.jobs(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists jobs_status_idx on public.jobs(status);
create index if not exists job_executions_job_id_idx on public.job_executions(job_id);
create index if not exists system_logs_created_at_idx on public.system_logs(created_at desc);
