-- Privileged database access stays inside Supabase Edge Functions.
-- The bridge secret hash is provisioned separately at deployment time and must never be committed.
create table if not exists public.hermes_bridge_secret (
  id boolean primary key default true check (id = true),
  secret_hash text not null,
  updated_at timestamptz not null default now()
);

alter table public.hermes_bridge_secret enable row level security;
revoke all on table public.hermes_bridge_secret from anon, authenticated;
grant select on table public.hermes_bridge_secret to service_role;
