alter table public.hermes_products
  add column if not exists job_id uuid,
  add column if not exists idempotency_key text,
  add column if not exists artifacts jsonb not null default '{}'::jsonb,
  add column if not exists paused boolean not null default false,
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists hermes_products_idempotency_key_uq
  on public.hermes_products(idempotency_key)
  where idempotency_key is not null;

create unique index if not exists hermes_jobs_idempotency_key_uq
  on public.hermes_jobs(idempotency_key)
  where idempotency_key is not null;

create unique index if not exists hermes_sales_events_provider_external_id_uq
  on public.hermes_sales_events(provider, external_id)
  where external_id is not null;

create index if not exists hermes_jobs_status_created_idx
  on public.hermes_jobs(status, created_at);

create index if not exists hermes_products_status_created_idx
  on public.hermes_products(status, created_at);
