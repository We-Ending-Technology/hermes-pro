create table if not exists public.hermes_opportunities (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  title text not null,
  url text not null,
  summary text not null default '',
  score integer not null default 0,
  difficulty text not null default 'unknown',
  suggested_price numeric(12,2),
  currency text not null default 'BRL',
  proposal text not null default '',
  status text not null default 'candidate',
  rejection_reason text,
  application_status text not null default 'not_attempted',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists hermes_opportunities_url_uq on public.hermes_opportunities(url);
create index if not exists hermes_opportunities_score_idx on public.hermes_opportunities(score desc, created_at desc);
create index if not exists hermes_opportunities_status_idx on public.hermes_opportunities(status, created_at desc);
