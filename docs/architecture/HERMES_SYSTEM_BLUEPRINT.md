# Hermes System Blueprint

**Status:** architecture contract and staged implementation plan  
**Scope:** private owner-operated command center; not a public SaaS  
**Primary principle:** build a dependable operating system for work, then add autonomy only behind evidence-based gates.

## 1. Product definition

Hermes is a private, extensible system that converts an owner's intent into safe, observable, recoverable work and—eventually—verified economic outcomes. It should reduce manual coordination, not hide uncertainty or fabricate progress.

The system grows incrementally. Each layer must have a stable contract, tests, health signals, and a rollback path before downstream layers depend on it. The domino metaphor describes dependency order; fault isolation must prevent one failed component from cascading through the whole system.

### Non-negotiable invariants

1. **One canonical production API and database.** Other services must call the canonical API or use explicitly documented database access; no accidental split-brain between old and new Render services.
2. **Durable state before claiming completion.** A task is accepted only after its intent/idempotency key is durably stored. Completion means persisted output plus evidence, not merely an HTTP 200.
3. **At-least-once delivery, effectively-once side effects.** Queue messages may repeat; every side-effecting operation must have an idempotency key, a recorded state transition, and reconciliation logic.
4. **Fail closed on dangerous actions.** Spending money, publishing, sending messages, applying to jobs, changing production secrets, or irreversible actions require explicit policy and authorization. Read-only discovery can have broader autonomy when lawful and permitted.
5. **No fake capability status.** Distinguish absent, configured, connected, tested, degraded, disabled, and verified-in-production. A registered agent is not a working agent.
6. **Owner-controlled pause and kill switch.** A global pause blocks new external side effects while preserving diagnostics, logs, queue state, and recovery.
7. **No secrets in source, logs, browser output, task payloads, or chat.** Credentials belong in the hosting secret store; rotate exposed credentials and use least privilege.
8. **Cost awareness.** Every metered integration has a budget, timeout, retry ceiling, and per-operation cost estimate. Never retry a paid action blindly.
9. **Evidence over claims.** Every consequential task records timestamps, input/output references, provider, attempts, state transitions, and a safe error summary.
10. **Compatibility before replacement.** Reuse working components; migrate through adapters and tests rather than rebuilding the project wholesale.

## 2. Dependency ladder (the domino chain)

A layer is promoted only after its exit criteria pass. Later layers must not bypass earlier ones.

| Layer | Capability | Required proof before moving on |
|---|---|---|
| L0 — Control plane | Owner identity, configuration, secrets, global pause, environment separation | No secret leakage; production configuration can be inspected safely |
| L1 — Runtime foundation | One official API, PostgreSQL identity/connectivity, migrations, health/readiness | Deploy and restart succeed; API points to the intended database |
| L2 — Durable work | Persistent jobs, state machine, idempotency, leases/locks, bounded retries, dead-letter/recovery | Create/read/execute/restart/recover test passes without duplicate side effects |
| L3 — Observability | Structured logs, correlation IDs, audit trail, health of dependencies, alerts | A failed task can be traced from request to storage to worker |
| L4 — Execution fabric | Separate worker, scheduler/cron, safe concurrency, cancellation, timeout and retry policies | Worker restart recovers work; API remains responsive under worker failure |
| L5 — Tool/capability registry | Typed tools, permissions, quotas, health, provenance, expiry and renewal metadata | Every tool exposes contract, authorization scope, cost and failure mode |
| L6 — Intelligence and agents | Chief/orchestrator, specialist agents, plans, bounded delegation, QA and recovery | Agents call only registered tools and produce testable outputs with evidence |
| L7 — Work products | File generation, artifact storage, versioning, checksums, signed/expiring links | PDF/DOCX/cover survive restart and can be retrieved and verified |
| L8 — Commercial operations | Offers, lead/opportunity records, approvals, delivery, invoices/payments, costs | One permitted transaction is traced from demand to confirmed payment |
| L9 — Controlled autonomy | Policy-driven schedules, approved channels, escalation, learning from outcomes | Multiple safe cycles run without duplicate actions, runaway costs, or silent failures |
| L10 — Scale and portfolio | Multiple revenue channels, isolated workloads, capacity limits, analytics | New modules can be added/removed without destabilizing the core |

## 3. Target runtime architecture

- **Web command center:** React/Vite PWA. It displays truth from the API; it does not hold privileged long-lived secrets.
- **Canonical API:** FastAPI. Owns authentication, authorization, validation, task admission, state transitions, and read models.
- **PostgreSQL:** source of truth for jobs, executions, idempotency, audit events, integrations, artifacts metadata, approvals, and financial ledger. Database schema changes are versioned migrations.
- **Worker:** independent process consuming durable jobs. It must claim jobs with a lease/lock, heartbeat long-running work, stop on cancellation, and recover expired leases.
- **Scheduler:** separate, single-owner scheduling mechanism (managed cron or database-backed scheduler with distributed lock). Avoid running an unconstrained scheduler in every API replica.
- **Object storage:** generated files and larger artifacts; database stores metadata, hashes, size, MIME type, owner, lifecycle policy, and storage key.
- **Integration adapters:** one interface per provider, with timeouts, quotas, health checks, explicit permissions, and normalized errors.
- **AI gateway:** provider-neutral contract, configured primary/fallback, token/cost budgets, bounded retries, and structured output validation.
- **Policy/approval layer:** decides whether an action is read-only, reversible, external, financial, public, or irreversible; enforces approvals and the kill switch.
- **Observability:** structured logs, request/job correlation IDs, metrics, audit events, alert routing, and redaction.
- **Recovery controller:** reconciles stale jobs and missing outputs; retries only when the operation is safe and idempotent; otherwise quarantines for review.

The existing repository already contains a FastAPI API, React/Vite frontend, PostgreSQL adapter, AI gateway, agent registry, product/job persistence, autonomy code, integrations and diagnostic tooling. Preserve and harden these before introducing parallel implementations.

## 4. Job lifecycle contract

Use explicit states and validated transitions:

`accepted -> queued -> running -> succeeded`

Failure path:

`running -> retry_wait -> queued` (only while attempts and retry policy allow)

Terminal paths:

`running -> failed_permanent | cancelled | needs_approval | dead_letter`

Required fields: stable job ID, idempotency key, job type/version, payload schema version, created/updated timestamps, attempt count and ceiling, next retry time, lease owner/expiry, correlation ID, policy/approval status, result/artifact references, and redacted error classification.

Rules:
- Persist before acknowledging task admission.
- Use exponential backoff with jitter for transient failures and strict retry ceilings.
- Never automatically retry an ambiguous payment, publish, message, or application side effect until reconciliation determines whether it already happened.
- Make state transitions atomic and compare-and-set/transactional.
- Store outputs before marking success; use checksums and verify retrieval.
- Keep terminal records and audit evidence according to a documented retention policy; archive large payloads instead of deleting operational history silently.
- Use a dead-letter queue and a recovery report. Recovery must be safe to run more than once.

## 5. Internet and tool access

Hermes should access the internet through a controlled capability registry, not unrestricted arbitrary actions by every agent.

Every connector/tool entry must define:
- provider and exact API/site;
- official API, documented automation route, or permitted browser workflow;
- auth method and scopes;
- actions allowed (read/search, draft, write, publish, purchase);
- rate limit, quota, cost, timeout and retry rules;
- data classification and redaction;
- credential expiry/renewal status and owner;
- health check, last successful test, and evidence;
- fallback provider and shutdown behavior.

Prefer official APIs and supported integrations. Use browser automation only where site terms and permissions allow it; respect robots/access controls, rate limits, privacy and anti-spam rules. Do not bypass CAPTCHAs, authentication barriers, paywalls, or platform restrictions. An available internet connection does not grant permission to perform every action.

Tool access is granted per capability and per action. Discovery may be read-only; sending, applying, publishing, buying, or modifying external data requires a stronger policy gate.

## 6. Credentials, expiry and lifecycle management

“Do not let things expire” means detect and manage expiry proactively—not pretend expiring credentials can be made permanent.

- Store secrets only in the host's secret manager/environment settings; never commit values.
- Maintain a non-secret integration inventory with secret reference/name, provider, scopes, owner, last validation, expiry if known, and renewal instructions.
- Alert before known expiry (for example, 30/14/7/1 days where the provider exposes expiry); use provider refresh-token rotation where officially supported.
- Distinguish credentials that expire, credentials that can be rotated, subscriptions/credits that renew, signed artifact URLs that are intentionally short-lived, and provider policies that can change.
- On authentication failure, classify it as expired/revoked/permission/rate-limit/temporary where evidence allows; pause affected actions, alert, and never loop retries.
- Rotate exposed credentials. Never print them in diagnostics.
- Test secrets by checking a minimal safe endpoint; never expose secret values in the UI.
- Add expiry metadata and reminders for certificates, domains, OAuth grants, webhooks, storage links, and scheduled tasks where relevant.

## 7. Safety, autonomy and spending

Each action receives a policy class:
- **A0 Read-only:** public retrieval, health checks, analysis.
- **A1 Internal reversible:** create internal drafts/tasks and run sandbox tests.
- **A2 External reversible:** permitted drafts or updates that can be undone.
- **A3 External consequential:** send, submit, publish, apply, or communicate as the owner; requires explicit grant, channel-specific rules and audit.
- **A4 Financial/irreversible:** purchases, paid API usage beyond a defined budget, payouts, deletion, or irreversible changes; explicit approval required unless a narrowly scoped standing budget has been configured.

Global kill switch blocks new A2-A4 operations, stops new discovery if configured, and cancels safe-to-cancel work. It must not delete queues or logs. Recovery/diagnostics remain available.

Every run has max wall time, max steps, max spend, max parallelism, max retries, and a termination condition. No infinite agent loops. No claim of revenue until a payment provider or reliable ledger confirms receipt.

## 8. Security and operational controls

- Separate development, preview and production credentials/resources.
- Use least-privilege service accounts and short-lived credentials when supported.
- Never place privileged API keys in browser bundles or local storage.
- Protect mutating endpoints, validate webhook signatures/tokens, and rate-limit sensitive routes.
- Use schema validation and versioning for job payloads and tool contracts.
- Apply database migrations with a rollback/forward-repair plan and backups before risky schema changes.
- Redact tokens, connection strings, personal data and provider payloads from logs.
- Keep an append-only audit trail for approvals, policy decisions, external actions, cost and outcomes.
- Add dependency and secret scanning to CI; require tests and successful deployment health before promoting releases.

## 9. Production truth dashboard

Show separate status for:
- deployment health;
- API authentication;
- database identity/connectivity;
- worker heartbeat and queue lag;
- scheduler ownership/last run;
- storage read/write verification;
- AI provider connectivity and quota;
- each integration's auth/permissions/expiry;
- failed, stale, retrying and dead-letter jobs;
- current and monthly metered cost;
- revenue received, refunds, fees and net profit;
- last end-to-end proof and its timestamp.

Do not label a component “working” solely because a key exists, a class is registered, a URL responds, or a deployment is live.

## 10. Implementation sequence

### Phase A — Establish production truth
1. Confirm the canonical Render API service, database identity, environment references and authentication behavior.
2. Fix any service-to-service references that point to retired or ambiguous services.
3. Run the authenticated diagnostic persistence/restart/idempotency test.
4. Record the result and deployment SHA as evidence; keep autonomy off until the test passes.

### Phase B — Make work durable
1. Move scheduled autonomy out of API lifespan into a single controlled scheduler.
2. Ensure the worker uses durable queue claims/leases, heartbeats, cancellation, retry ceilings and dead-letter handling.
3. Add stale-job reconciliation and safe recovery tests.
4. Add correlation IDs and structured audit/state-transition events.

### Phase C — Verify artifacts end to end
1. Generate one low-cost test artifact using a provider configured and budget-approved.
2. Verify cover, PDF and DOCX uploads, checksums, content types, sizes, download and retrieval after restart.
3. Test provider failure, timeout, duplicate request, and recovery without duplicate artifacts.
4. Never claim an upload succeeded without verifying stored bytes.

### Phase D — Activate one economic loop
1. Select one lawful service offer and one authorized acquisition channel.
2. Build a reproducible demo and automated QA.
3. Keep the user's previously paused opportunity radar paused unless explicitly resumed.
4. Require approval for external applications/messages until official authorization, channel policy and kill switch are verified.
5. Track work, delivery, payment confirmation, fees, refunds and net profit.

### Phase E — Expand by plug-in contracts
Add capabilities only through the registry, permission model, tests, observability, cost/expiry metadata and rollback plan. New capabilities must not create a second source of truth or bypass the job lifecycle.

## 11. Definition of done for a capability

A capability is complete only when all apply:
- implementation merged and deployed to the intended service;
- automated tests pass;
- authorization and policy behavior tested;
- positive and negative paths tested;
- timeout/retry/idempotency/restart behavior tested where applicable;
- evidence is persisted and visible;
- costs and expiry behavior are documented;
- health/alerting and rollback path exist;
- production behavior was observed and clearly labeled as verified or unverified.

## 12. Immediate engineering priority

Do not add more agents or revenue channels yet. First prove the production foundation (API + PostgreSQL + durable diagnostic job + restart recovery). Then harden the durable worker/scheduler boundary. That is the load-bearing domino: all later autonomy depends on it.
