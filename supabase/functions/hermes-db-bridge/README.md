# Hermes Supabase DB bridge

This function is the server-side fallback for Hermes when the Render service does not have a Supabase secret key.

## Security model

- Supabase's privileged API key remains inside the Edge Function runtime.
- Render sends only the public/publishable API key plus `x-hermes-bridge-key`.
- The bridge secret is stored in Render as `SUPABASE_BRIDGE_SECRET`; only its SHA-256 hash is stored in `public.hermes_bridge_secret`.
- The bridge compares hashes in constant time and never returns the stored hash.
- The bridge refuses access to its own secret table and accepts only GET, POST, PATCH, and DELETE requests to simple table names.
- Do not commit the bridge secret or a Supabase secret/service-role key.

## Required runtime configuration

Render:
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_BRIDGE_SECRET`

Supabase Edge Function runtime:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEYS` (preferred) or legacy `SUPABASE_SERVICE_ROLE_KEY`

The function must be deployed with JWT gateway verification disabled because it authenticates its own bridge header. Do not expose the bridge secret to browser clients.
