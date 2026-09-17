# Hermes Autonomous Memory, Reflection & Watchdog Design

## Goal

Make Hermes operate as a persistent autonomous team: remember verified lessons, reflect periodically, detect failures without a human prompt, delegate work through a CEO/orchestrator, and act only within explicit autonomy and budget rules.

## Architecture

Hermes adds five cooperating subsystems:

1. **Memory Engine** — persistent lessons, incidents, procedures, preferences, and experiment outcomes in Supabase. Memory is evidence-backed and confidence-scored; raw chat is not automatically promoted to permanent memory.
2. **Reflection/Dreaming Engine** — periodically reviews recent events/incidents/jobs and proposes durable lessons. Only validated lessons are promoted.
3. **Event/Watchdog Engine** — continuously evaluates health, stalled jobs, repeated provider failures, failed deployments/integrations, budget anomalies, and unresolved incidents. It creates idempotent incidents and wakes the CEO without user prompting.
4. **Agent Hierarchy** — a CEO agent coordinates specialist agents. Specialists own diagnosis, operations, QA, radar, product, sales, analytics, guardian, and memory/reflection responsibilities. The CEO delegates rather than duplicating specialist logic.
5. **Autonomy Policy** — every automated action is classified as observe, reversible, financially bounded, or human-approval-required. Kill switch, daily budget, idempotency, retry ceilings, and escalation rules are enforced before execution.

## Persistent data

Add versioned migrations for:

- `hermes_memories`: durable lessons with category, statement, evidence, confidence, verification count, status, and timestamps.
- `hermes_incidents`: detected problems with fingerprint, severity, status, diagnosis, action, resolution, attempts, and escalation state.
- `hermes_watchdog_checks`: last run/result for each health rule.
- `hermes_reflections`: reflection runs and promoted/rejected lesson counts.
- `hermes_autonomy_policies`: action-level limits and approval requirements.

All exposed tables retain RLS. Server-side persistence must use the configured Supabase secret/service key; no secret is ever sent to the frontend.

## Memory lifecycle

`event -> candidate lesson -> evidence check -> promote/reject -> reuse -> re-verify`.

A lesson can be `candidate`, `active`, `stale`, or `rejected`. Active lessons require evidence. Contradictory evidence lowers confidence and can make a lesson stale instead of silently overwriting history.

## Watchdog lifecycle

`scheduled check -> detect -> fingerprint -> incident -> CEO triage -> specialist -> guarded action -> verify -> resolve/escalate -> memory candidate`.

Checks must be cheap and idempotent. Repeated identical failures update one incident rather than creating an incident storm.

## Agent hierarchy

- `CEO`: prioritizes and delegates.
- `Watchtower`: detects health and operational anomalies.
- `Diagnostic`: investigates evidence and identifies likely root cause.
- `Guardian`: enforces kill switch, budget, risk, and policy boundaries.
- `Memory`: retrieves and records lessons.
- `Reflection`: consolidates recent evidence into durable lessons.
- Existing commercial specialists remain available for Radar, Product, Service, Design, Document, QA, Publisher, Sales, Analytics, Optimizer.

The hierarchy is deterministic at the policy boundary. LLM output may propose an action, but the policy engine decides whether it is executable.

## Autonomous actions

Allowed automatically when policy permits:

- health checks and diagnostics;
- retries of idempotent jobs;
- provider failover;
- restarting/requeueing stuck jobs;
- regenerating failed product artifacts;
- updating internal status and logs;
- creating opportunity/product jobs inside configured budget.

Require human approval unless an explicit policy says otherwise:

- irreversible external publication when unsupported by a verified adapter;
- refunds, financial transfers, legal commitments;
- changing credentials/security configuration;
- actions exceeding configured spend/risk limits.

## Reflection schedule

The existing 15-minute autonomous cycle remains the operational heartbeat. Reflection runs on a slower cadence and only when enough new evidence exists. It can also be triggered after a resolved incident. Reflection must never block normal production jobs.

## Failure behavior

No exception is silently swallowed by the autonomy layer. Operational errors are recorded as incidents/events. A failed autonomous action gets bounded retries, then escalation. The system must never claim that a problem was fixed unless a verification check succeeds.

## Success criteria

1. A verified correction is retrievable on a later autonomous cycle.
2. A repeated failure creates one incident fingerprint, not duplicate storms.
3. A stalled job is detected and safely requeued/retried without duplicate product creation.
4. The CEO delegates a diagnostic task and records the outcome.
5. Reflection promotes only evidence-backed lessons.
6. Kill switch and budget policy can block an otherwise proposed action.
7. A resolved incident becomes a candidate lesson for future cycles.
8. Restarting the API does not erase memory, incidents, or watchdog state.
9. No secret or privileged Supabase credential reaches the frontend.
10. Tests cover policy boundaries, memory promotion, watchdog deduplication, and autonomous recovery.
