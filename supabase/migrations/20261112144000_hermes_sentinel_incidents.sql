create table if not exists public.hermes_incidents (
  id uuid primary key default gen_random_uuid(),
  component text not null,
  symptom text not null,
  probable_cause text not null,
  action text not null,
  result text not null,
  status text not null default 'open' check (status in ('open','resolved')),
  attempts integer not null default 1,
  requires_human boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  resolved_at timestamptz
);

create unique index if not exists hermes_incidents_one_open_per_component
  on public.hermes_incidents(component)
  where status = 'open';

create index if not exists hermes_incidents_created_idx
  on public.hermes_incidents(created_at desc);

alter table public.hermes_incidents enable row level security;
revoke all on table public.hermes_incidents from anon, authenticated;
grant all on table public.hermes_incidents to service_role;
