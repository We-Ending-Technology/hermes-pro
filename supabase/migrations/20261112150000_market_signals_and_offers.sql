create table if not exists public.hermes_market_signals (
  id uuid primary key default gen_random_uuid(),
  niche text not null,
  source text not null,
  source_url text not null,
  demand_estimated numeric,
  competition numeric,
  evidence jsonb not null default '{}'::jsonb,
  data_consulted timestamptz not null default now(),
  positive boolean not null default false
);

create index if not exists hermes_market_signals_niche_date_idx
  on public.hermes_market_signals(lower(niche), data_consulted desc);

create table if not exists public.hermes_offers (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.hermes_products(id) on delete restrict,
  price numeric(12,2) check (price is null or price > 0),
  link_checkout text,
  status text not null default 'draft' check (status in ('draft','active','paused')),
  approval_required boolean not null default true,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists hermes_offers_product_idx
  on public.hermes_offers(product_id, created_at desc);

create unique index if not exists hermes_offers_one_draft_per_product
  on public.hermes_offers(product_id)
  where status = 'draft';
