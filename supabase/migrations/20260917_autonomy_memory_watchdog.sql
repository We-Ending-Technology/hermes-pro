create table hermes_memories (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  statement text not null,
  evidence jsonb not null default '{}'::jsonb,
  confidence numeric not null default 0,
  verification_count integer not null default 0,
  status text not null default 'candidate',
  source_type text,
  source_id text,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index hermes_memories_status_confidence_idx on hermes_memories(status, confidence desc);

create table hermes_incidents (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,
  kind text not null,
  severity text not null default 'warning',
  status text not null default 'open',
  summary text not null,
  evidence jsonb not null default '{}'::jsonb,
  diagnosis jsonb not null default '{}'::jsonb,
  action jsonb not null default '{}'::jsonb,
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  requires_human boolean not null default false,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index hermes_incidents_status_idx on hermes_incidents(status, severity, last_seen_at desc);

create table hermes_watchdog_checks (
  id uuid primary key default gen_random_uuid(),
  check_name text not null unique,
  last_run_at timestamptz,
  last_status text,
  last_fingerprint text,
  last_result jsonb not null default '{}'::jsonb,
  run_count integer not null default 0,
  failure_count integer not null default 0,
  updated_at timestamptz not null default now()
);

create table hermes_reflections (
  id uuid primary key default gen_random_uuid(),
  trigger_type text not null,
  input_window jsonb not null default '{}'::jsonb,
  candidate_count integer not null default 0,
  promoted_count integer not null default 0,
  rejected_count integer not null default 0,
  summary text,
  created_at timestamptz not null default now()
);

create table hermes_autonomy_policies (
  id uuid primary key default gen_random_uuid(),
  action text not null unique,
  mode text not null default 'reversible',
  enabled boolean not null default true,
  requires_approval boolean not null default false,
  max_cost numeric not null default 0,
  max_attempts integer not null default 3,
  notes text,
  updated_at timestamptz not null default now()
);

alter table hermes_memories enable row level security;
alter table hermes_incidents enable row level security;
alter table hermes_watchdog_checks enable row level security;
alter table hermes_reflections enable row level security;
alter table hermes_autonomy_policies enable row level security;

insert into hermes_autonomy_policies (action, mode, requires_approval, max_cost, max_attempts, notes)
values
  ('observe', 'observe', false, 0, 1, 'Read-only diagnostics and health checks'),
  ('retry_job', 'reversible', false, 0, 3, 'Retry only idempotent jobs'),
  ('provider_failover', 'reversible', false, 0, 3, 'Use configured provider/key failover'),
  ('produce', 'financially_bounded', false, 0, 3, 'Product generation inside configured budget'),
  ('publish', 'human_approval', true, 0, 1, 'External publication requires explicit channel capability/approval'),
  ('refund', 'human_approval', true, 0, 1, 'Financially consequential action'),
  ('credential_change', 'human_approval', true, 0, 1, 'Security-sensitive action')
on conflict (action) do nothing;
