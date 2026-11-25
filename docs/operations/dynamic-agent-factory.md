# Hermes Pro — Dynamic Agent Factory

## Scope

This change adds a persistent registry for specialist agents, independent execution records, operational memory, owner approval, and bounded delegation by Hermes Chefe.

## Safety model

- New specialists are created as `draft`; they cannot run until explicitly approved through the private API.
- The migration seeds the existing code-defined Hermes team as approved system agents.
- The only capability currently implemented is `analysis`.
- The only permission scopes are `ai.complete`, `memory.read`, and `memory.write`.
- The tool allowlist must remain empty. Publishing, payments, billing, account administration, secret access, code deployment, and external writes are not available to dynamic agents.
- Execution and AI-generated agent proposals are disabled by default. The backend setting `DYNAMIC_AGENT_EXECUTION_ENABLED` defaults to `false`.
- Prompts are not copied into operational memory or run input. The run record stores prompt length and SHA-256 fingerprint; the output and provider/model are stored for audit.
- Chief delegation is bounded to three approved specialists and records a shared correlation ID.
- A failed execution is recorded with its error class and increments operational memory; the system does not silently retry an AI call.

## API (all routes require X-Hermes-API-Key)

- `GET /api/v1/agent-factory/agents`
- `POST /api/v1/agent-factory/agents` — create a draft.
- `POST /api/v1/agent-factory/agents/{id}/activate` — requires `approved: true` and an approval note.
- `POST /api/v1/agent-factory/agents/{id}/disable`
- `POST /api/v1/agent-factory/agents/{id}/run` — only approved active agents; execution feature flag must be enabled.
- `POST /api/v1/agent-factory/chief/propose-agent` — Chief proposes a draft; execution feature flag must be enabled.
- `POST /api/v1/agent-factory/chief/delegate` — independently runs 1–3 active specialists; execution feature flag must be enabled.
- `GET /api/v1/agent-factory/runs`

## Migration and rollout

1. Review this PR and its CI results.
2. Apply `20261123150000_dynamic_agent_factory.sql` to the staging database first, then validate registry reads, seed rows, RLS, approval constraints, and execution history.
3. Do not apply the migration to production until the owner approves the exact SQL and rollback plan.
4. Merge only after CI passes.
5. Deploy the API after the migration exists. The new endpoints will return a controlled 503 until the database migration is applied.
6. Keep `DYNAMIC_AGENT_EXECUTION_ENABLED=false` initially. Enable only after the AI provider's billing/quota tier and the owner's zero-spend policy have been checked.
7. Test with a stubbed provider in CI. Do not consume production Gemini quota for smoke tests.

## Rollback

The forward migration is additive and does not modify or delete existing tables. If rollback is required after deployment, first disable dynamic execution and remove the new router from the API release. Drop the new execution table before the agent registry only after confirming there are no required audit records. Do not delete the shared `hermes_agent_memory` table.
