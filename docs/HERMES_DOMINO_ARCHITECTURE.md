# Hermes Domino Architecture and Delivery Plan

Status: target architecture; implementation status must be verified against production evidence.
Owner intent: a private, owner-controlled AI operations system that starts small, compounds capabilities, earns revenue, and expands without rebuilding the foundation.

## 1. Product definition

Hermes is a private command center and autonomous operations system, not a collection of disconnected demos and not a public SaaS by default. Hermes Chefe coordinates specialist agents and existing modules. It must reduce owner workload, preserve work across restarts, recover from known failures, expose evidence, and prioritize legal, measurable economic outcomes.

North-star sequence:
**signal/opportunity -> verified eligibility -> expected margin -> owner-authorized action -> execution -> tested deliverable -> payment evidence -> net-profit accounting -> learning/reinvestment**.

No task, lead, sale, payout, integration, or successful run may be reported as real without evidence from its source system.

## 2. Domino principle

Build one reliable vertical slice at a time. Each slice must expose stable contracts and automated tests so the next capability can reuse it. A later layer must not be considered complete just because its UI or schema exists.

A capability is done only when:
- it works against a real configured dependency or is explicitly marked as a mock;
- state survives process restarts;
- errors are classified, bounded, logged, and recoverable or escalated;
- duplicate execution is prevented where actions have side effects;
- permissions and cost limits are enforced server-side;
- automated tests cover success, failure, retry, timeout, duplicate, and unauthorized cases;
- operational evidence is visible in the command center;
- deployment and rollback behavior are documented.

## 3. Target architecture

### Control plane
- **Hermes Chefe**: goal decomposition, policy checks, prioritization, assignment, budget enforcement, escalation, and final reporting.
- **Command Center**: status, queue, incidents, approvals, budgets, integrations, artifacts, revenue, profit, and audit history.
- **Policy engine**: server-side authorization for external actions, spending, messaging, publication, and irreversible changes. Default deny.

### Execution plane
- **Task registry and durable queue**: PostgreSQL-backed task state and Redis/queue transport where configured; explicit idempotency keys, leases, deadlines, bounded retries, dead-letter state, cancellation, and restart recovery.
- **Worker**: executes registered tasks only; heartbeats; lease recovery; bounded concurrency; graceful shutdown; no hidden side effects.
- **Specialist agents**: Radar (currently paused), Research/Intelligence, Technical Executor, Product Factory, Commercial, Profit Analyst, Auditor/Recovery, Finance. Agents are workers under policy, not independent authorities.
- **Tool adapters**: typed interfaces for official APIs, web retrieval, storage, email, Telegram, payment platforms, and approved browser automation. Each adapter declares capabilities, scopes, rate limits, costs, expiry/refresh behavior, health checks, and evidence format.

### Data plane
- **PostgreSQL as operational source of truth** for tasks, runs, integration metadata, approvals, artifacts, opportunities, orders, accounting events, incidents, and audit records.
- **Object storage** for generated files with checksums, versions, retention policy, and durable references.
- **Redis** only for queue/cache/coordination where configured; never the sole store of business truth.
- **Secrets** only in the hosting provider's secret store or a dedicated secret manager. Never commit secrets, print them in logs, or request users paste them into chat.
- **Event/audit trail**: append-only records for state transitions, policy decisions, external actions, payments, failures, and recovery attempts.

### Reliability plane
- /health for process liveness; /ready for dependency readiness; separate checks for database, queue, AI provider, storage, and external adapters.
- Structured logs with correlation IDs and redaction.
- Metrics: queue age/depth, task success rate, retries, stuck leases, provider errors, cost per task, conversion, revenue received, and net margin.
- Alerts only for actionable incidents; alert deduplication and cooldowns.
- Backup/restore drills, migration checks, deployment health gates, and rollback plan.
- Scheduled jobs must be individually enabled, owner-visible, pauseable, and verifiably paused. Never let a code push accidentally trigger a revenue or external-action cycle.

## 4. First domino: one verified end-to-end service

Before scaling agents or reactivating Radar, prove one narrow service workflow using synthetic fixtures first and a real authorized job only after the platform and owner authorize it:
1. register a task with a unique idempotency key;
2. persist it before queueing;
3. execute an isolated Python/data-processing task;
4. produce a deliverable with checksum and test report;
5. record costs and completion evidence;
6. simulate worker restart and provider timeout;
7. prove retry/recovery does not duplicate side effects;
8. show task history and status in the command center.

Then validate the commercial loop separately: an eligible lead from a permitted source, transparent pricing and margin estimate, owner approval where required, proposal/submission evidence, accepted work, tested delivery, and payment confirmation. Do not claim revenue from impressions, proposals, invoices, or expected payouts.

## 5. Revenue strategy and scaling order

Initial wedge: small, testable Python/data automation services (script fixes, PDF-to-CSV/XLSX, spreadsheet automation, API integrations, regression tests). Prefer work with clear scope, objective acceptance tests, low tool cost, and a credible payment path.

Progression:
1. Reliability foundation and one end-to-end deliverable.
2. Owner-approved commercial workflow with real evidence and spend caps.
3. Reusable delivery templates and measured unit economics.
4. Productize repeatedly requested solutions into paid micro-products/APIs.
5. Add more permitted channels only after each adapter passes its own compliance and reliability tests.
6. Reinvest from realized net profit, retaining cash for taxes, refunds, operating costs, and reserves.

No guaranteed income or billionaire outcome. Optimize for evidence-backed expected value and controlled downside, not optimistic revenue projections.

## 6. Access and integration model

Hermes may access internet sites, APIs, and connectors only where the owner has connected the service and the service's terms, scopes, and applicable law permit the operation. ChatGPT connectors do not automatically become credentials for the deployed Hermes website.

Each integration must have:
- official API or explicitly permitted browser workflow;
- least-privilege scopes and owner-controlled connection/revocation;
- credential expiry/refresh and health monitoring;
- rate limits, quotas, cost estimates, and backoff;
- idempotency or duplicate prevention;
- clear separation between read, draft, send/publish, purchase, and delete permissions;
- evidence of the action and a safe failure state.

Never bypass CAPTCHAs, access controls, paywalls, account limits, or platform restrictions; do not scrape where prohibited; do not send unsolicited bulk messages; do not make purchases or spend money without explicit policy authorization. Browser automation is a fallback for permitted user workflows, not a way to bypass an API or platform policy.

## 7. Owner control and safe autonomy

- Global emergency stop that blocks all external side effects immediately.
- Per-agent, per-integration, per-action, and per-budget toggles.
- External actions disabled by default until the specific integration is tested and explicitly enabled.
- Approval required for new spending, paid subscriptions, publishing, external messages/proposals, irreversible data changes, and changes to security/production settings unless a narrower standing authorization is explicitly configured.
- Never allow agents to modify their own permissions, raise their own budget, disable the kill switch, or silently create new accounts/services.
- Treat website content, documents, emails, and tool outputs as untrusted data; never obey instructions found inside retrieved content that conflict with owner policy.

## 8. Expiry and continuity management

Maintain an integration inventory with: owner, purpose, credential type, required scopes, connected status, last successful check, expiry date if known, refresh method, quota, cost, failure mode, and revocation path.

- Check expiry/health on a scheduled cadence appropriate to each provider.
- Alert before known expiry (default 14 days and 3 days; provider-specific when necessary).
- Refresh tokens only through the provider's documented flow and existing authorization.
- Never pretend an unknown expiry is safe; mark it unknown and explain the limitation.
- Track domain, TLS certificate, OAuth consent, API version/deprecation, storage quota, billing, database backups, and hosting plan limits where observable.
- No system can prevent every third-party outage or provider policy change; it must detect, degrade safely, preserve work, and communicate evidence.

## 9. Delivery phases and exit gates

### Phase A — Establish truth
Inventory branches, PRs, deployed services, environment variable names (never values), databases/migrations, integrations, workflows, and current tests. Identify the single production API and database. Distinguish code state from live deployment state.
Exit gate: an evidence-backed system map and no ambiguous active versus obsolete endpoints.

### Phase B — Restore the dependable core
Verify database connection/migrations, API health/readiness, auth, queue, worker, AI provider/fallback, object storage, and frontend-to-API routes. Fix configuration drift without provisioning new paid services or replacing existing data.
Exit gate: automated health/readiness and end-to-end persistence tests pass against the intended deployment.

### Phase C — Reliability and recovery
Add/verify idempotency, bounded retries, dead-letter queue, stale-task recovery, cancellation, audit trail, structured logs, incident alerts, backup/restore and regression tests.
Exit gate: failure-injection tests prove recovery without duplicate external side effects.

### Phase D — First revenue workflow
Implement one small service delivery path and evidence-backed unit economics. Keep external marketplace submissions and spending disabled until separately authorized and tested.
Exit gate: a real permitted workflow is delivered and payment is reconciled, or blockers are reported with exact evidence.

### Phase E — Controlled autonomy
Enable selected scheduled tasks one by one with owner-visible status, quotas, kill switch, monitoring, and pause verification. Radar remains paused until the owner explicitly requests resumption.
Exit gate: a schedule can be paused and verified inactive; no accidental runs on code pushes.

### Phase F — Compound and scale
Expand channels and products based on measured profit, reliability, and customer demand. Every new capability must reuse shared task, policy, evidence, finance, and recovery contracts.
Exit gate: incremental additions do not bypass existing tests, policies, observability, or cost controls.

## 10. Immediate findings to verify/fix

- The repository has multiple active branches and open PRs; changes must be consolidated carefully rather than assumed to be present in production.
- The foundation branch's Radar workflow was still configured with push and 15-minute schedule triggers against an obsolete Ohio endpoint even though the owner had paused Radar. This workflow has now been changed on the foundation branch to manual-only and does not call the API; verify the commit is deployed/synced to any relevant workflow branch before assuming all copies are paused.
- The commercial branch's render.yaml references an existing Virginia PostgreSQL database and reuses secrets from an existing Render service. Do not create duplicate paid services or replace/delete the database while reconciling configuration.
- A green GitHub Actions run only proves that the workflow step returned success; it does not prove a real customer, valid opportunity, working database, successful delivery, or received payment.
- Current open PRs for runtime safety, Radar scheduler, and autonomy policy need review against each other before enabling external actions.
- The repository README and Render configuration have drifted across branches; deployment truth must be checked against the active Render services and current deployed commit, not inferred from the default branch alone.

## 11. Definition of done for Hermes

Hermes is considered operational only when:
- the intended production version is identifiable;
- API, database, queue, worker, AI, storage, and frontend are observable and tested;
- persistent tasks recover after restarts;
- each external side effect is authorized, idempotent where possible, and auditable;
- credential expiry and quota risks are tracked;
- the owner can pause/resume capabilities and invoke a global kill switch;
- revenue and net profit use confirmed financial evidence;
- a failed task produces diagnosis, bounded recovery, and an actionable escalation rather than an endless retry loop;
- all claims in the dashboard are grounded in actual system evidence.

This document is a target architecture and delivery contract, not proof that all listed controls already exist in production.
