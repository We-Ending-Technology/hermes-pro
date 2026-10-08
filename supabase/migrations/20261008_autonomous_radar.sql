create table if not exists public.hermes_opportunities (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('product','service')),
  title text not null,
  description text,
  source text,
  source_url text,
  signals jsonb not null default '{}'::jsonb,
  score numeric,
  confidence numeric,
  status text not null default 'candidate',
  idempotency_key text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  url text,
  summary text not null default '',
  difficulty text not null default 'unknown',
  suggested_price numeric(12,2),
  currency text not null default 'BRL',
  proposal text not null default '',
  application_status text not null default 'not_attempted'
);
alter table public.hermes_opportunities
  add column if not exists url text,
  add column if not exists summary text not null default '',
  add column if not exists difficulty text not null default 'unknown',
  add column if not exists suggested_price numeric(12,2),
  add column if not exists currency text not null default 'BRL',
  add column if not exists proposal text not null default '',
  add column if not exists application_status text not null default 'not_attempted';
update public.hermes_opportunities set url=source_url where url is null;
create unique index if not exists hermes_opportunities_idempotency_uq on public.hermes_opportunities(idempotency_key) where idempotency_key is not null;
create unique index if not exists hermes_opportunities_url_uq on public.hermes_opportunities(url) where url is not null;
create index if not exists hermes_opportunities_score_idx on public.hermes_opportunities(score desc,created_at desc);
alter table public.hermes_opportunities enable row level security;
revoke all on public.hermes_opportunities from anon, authenticated;
