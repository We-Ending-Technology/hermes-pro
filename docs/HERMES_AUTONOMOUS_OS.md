# Hermes — Autonomous Work Operating System

## Product objective

Hermes is a private, owner-operated command center that turns natural-language goals into controlled, verifiable work. It discovers opportunities, evaluates feasibility and net economics, prepares deliverables, coordinates specialized agents, tracks external actions, and records outcomes. It must never represent plans, drafts, submissions, sales, or payments as completed unless evidence supports the claim.

## Operating principles

1. Evidence over assertion: every important state transition has a timestamp, actor, result, and evidence reference.
2. Persist before executing: long-running work is represented in durable storage before a worker acts.
3. Recover safely: retries are bounded, idempotent where possible, and never blindly repeat external side effects.
4. Least privilege: each agent gets only the tools and credentials required for its assigned work.
5. Human approval at risk boundaries: spending, external submission, publication, destructive changes, and irreversible actions require the configured approval gate.
6. Cost-aware autonomy: every run has limits for time, retries, model usage, and spend.
7. Honest status: configured, connected, tested, submitted, accepted, paid, and profitable are distinct states.
8. Graceful degradation: if a dependency fails, preserve the work, report the exact blocker, and continue independent steps where safe.

## Command center

- Chat: natural-language requests, attachments, task progress, approvals, evidence, and history.
- Chief: plans and coordinates work; it does not pretend to execute tools it did not call.
- Radar: discovers public/API-permitted opportunities, deduplicates records, preserves source URLs and collection timestamps, and scores fit.
- Analyst: estimates requirements, effort, risk, conversion uncertainty, platform fees, and net margin.
- Executor: creates code and artifacts in a controlled environment and records test results.
- Product factory: creates and validates e-books, templates, spreadsheets, reports, and commercial assets.
- Commercial: drafts tailored proposals and tracks external submission only when the integration confirms it.
- Auditor/recovery: detects failed or stuck tasks, attempts bounded safe recovery, validates the result, and escalates human-only blockers.
- Finance: distinguishes estimates, quoted amounts, pending payouts, confirmed receipts, refunds, costs, and realized net profit.

## Required task lifecycle

requested -> planned -> queued -> running -> awaiting_approval | succeeded | failed | cancelled

Every task should have a stable ID, idempotency key where applicable, owner, agent, tool calls, timestamps, attempt count, budget, status, error summary, artifact references, and evidence. A retry must resume from a safe checkpoint. External actions must use provider IDs and idempotency controls when supported.

## Revenue workflow

discover -> deduplicate -> qualify -> estimate_net_value -> prepare -> quality_check -> approval_gate -> submit/publish -> verify -> reconcile_payment -> learn

Discovery or a generated proposal is not revenue. Payment is counted only after a trustworthy provider record, webhook, or reconciled account evidence confirms receipt. Report gross revenue, fees, infrastructure/AI cost, refunds, net received, and estimated labor separately.

Initial low-cost channel: small, well-scoped freelance automation, data transformation, report generation, and bug-fix work. Secondary channels: digital products, direct business services, affiliates/partnerships, and validated microservices. Prioritize one working revenue loop before expanding channels.

## Tooling and safety

- Use official APIs or authorized browser automation; comply with each platform's terms.
- Keep secrets in deployment secret stores, never in code, chat, logs, or generated artifacts.
- Isolate execution of generated or user-supplied code.
- Require approvals for spending, external submissions, publishing, destructive actions, and permissions changes.
- Provide a global kill switch and per-agent pause/cancel.
- Treat web pages, files, emails, and customer content as untrusted data, not policy or system instructions.
- Apply rate limits, quotas, concurrency locks, bounded retries, and circuit breakers.
- Do not expose private customer data to tools without a valid need and permission.

## Reliability and recovery

- PostgreSQL is the source of truth for tasks, opportunities, approvals, artifacts, and financial events.
- Redis/queue is transport, not the only storage for task state.
- Scheduled work must have leases/heartbeats or equivalent stale-task detection.
- On restart, reconcile queued/running tasks and resume only safe operations.
- Use schema migrations, backups, restore drills, structured logs, health/readiness endpoints, alerts, and deployment rollback.
- Do not claim 24/7 availability on free infrastructure; design for interruption and recovery.

## Chat tool contract

The chat may answer conversationally, but explicit operational commands must route to real tools and return structured action/evidence metadata. The first vertical slice supports explicit Radar-cycle commands and system-status diagnostics. Unknown requests remain conversational and must not claim actions occurred.

## Acceptance criteria

1. A chat command can trigger a real Radar cycle and return counts plus execution evidence.
2. A system-status command returns actual dependency state.
3. API authentication protects operational POST routes.
4. PostgreSQL read/write and restart recovery are tested against the deployed database.
5. Duplicate opportunity scans do not create duplicate records or jobs.
6. An interrupted task can be recovered without duplicating external effects.
7. Every external submission or publication has provider-confirmed evidence.
8. Sales dashboards separate forecast, submitted proposals, accepted work, gross sales, fees, refunds, and cash received.
9. Budget exhaustion stops new paid model/tool calls and notifies the owner.
10. End-to-end tests cover missing credentials, unavailable dependencies, retries, duplicate requests, and rollback.

## Delivery sequence

- P0: stabilize PostgreSQL, provider credentials, auth, environment variables, and deployment alignment.
- P1: chat-to-tool execution, evidence responses, durable tasks, and integration tests.
- P2: real opportunity discovery, deduplication, ranking, and cost-aware qualification.
- P3: verified freelance workflow and one paid service delivery.
- P4: product publishing and payment reconciliation.
- P5: recovery, monitoring, budget guards, approvals, and kill switch.
- P6: additional agents, browser workflows, voice, and new revenue channels based on measured ROI.