# Hermes Commerce V2 — Architecture and Migration Contract

## Mission
Private, single-owner autonomous commerce system. Its job is to create and sell useful digital products with minimal owner attention, then measure actual revenue. This is not a public SaaS and not a freelance-opportunity radar.

## Non-negotiable operating rules
- Never report planned, queued, attempted, generated, published, paid, or revenue-confirmed as the same state.
- A product is publishable only after content, layout, assets, PDF/DOCX rendering, file integrity, and delivery have passed deterministic checks.
- A product is published only after the platform confirms its product/offer ID and a public checkout URL is verified.
- A sale is revenue only after a provider event is authenticated, deduplicated, and reconciled with the provider's transaction record.
- No paid API, hosting, storage, ads, upgrades, or purchases without explicit cost approval.
- No deletion or retirement of the old system until the replacement has passed migration and rollback checks.
- Freelance radar and opportunity-pipeline jobs remain paused unless the owner explicitly resumes them.
- Do not use Grok. AI providers must be explicitly configured and health-checked.

## Target architecture
1. Command Center — private UI for missions, products, publication, sales, incidents, approvals, costs, and audit history.
2. Chefe / Orchestrator — durable workflow coordinator. It creates typed tasks, assigns specialists, enforces gates, handles retries, and records evidence.
3. Specialists — market research, product strategy, authoring, fact-checking, editorial QA, illustration/cover, file rendering, publishing, growth analytics, finance/reconciliation, security/audit, and memory/evaluation.
4. Durable data plane — managed PostgreSQL as the source of truth for products, tasks, state transitions, approvals, incidents, provider events, and sales. Queue state must survive worker restarts; Redis may accelerate dispatch but is never authoritative.
5. Artifact storage — object storage with stable object keys and checksums. Store PDFs, DOCX, covers, source content, and manifests. Do not rely on expiring signed URLs as permanent references.
6. Workers and scheduler — separate API, worker, and scheduler processes. Jobs use leases, heartbeats, bounded retries, exponential backoff, idempotency keys, dead-letter handling, and replay.
7. Integrations — Kiwify first for product/offer/checkout/sales/webhooks; additional platforms only after a working end-to-end Kiwify transaction cycle. Keep credentials in managed environment secrets, never in Git or logs.
8. Resilience — provider fallback, circuit breakers, timeouts, quota-aware backoff, health checks, automatic recovery, and an owner-visible incident report. A sleeping/free host is not described as 24/7.
9. Memory and learning — persistent decisions, product outcomes, failure fingerprints, evaluations, and policy changes with versioning. No uncontrolled self-modification of production code.

## Agent contracts
Every specialist must declare: input schema, output schema, allowed tools, cost ceiling, timeout, retry policy, side-effect permissions, and deterministic acceptance tests. The Chefe validates outputs before state transitions. A role prompt inside one model call is not represented as an independently running agent.

## Product lifecycle
idea -> researched -> approved_for_production -> drafting -> editorial_review -> asset_generation -> render_validation -> ready_to_publish -> publishing -> published -> sale_observed -> reconciled
Failure paths are explicit (blocked, retry_wait, dead_letter, rejected, paused). Each transition records actor, timestamp, reason, and evidence.

## Commercial acceptance tests
- Create a product from a researched brief with a traceable source record.
- Generate a substantial, structured ebook with illustrations and a cover.
- Render PDF and DOCX; verify page count, text extraction, file size, image count, and checksums.
- Upload artifacts and verify download delivery using non-expiring object keys.
- Create the product and offer through the provider's supported integration.
- Verify checkout URL and delivery settings.
- Receive an authenticated provider webhook, deduplicate it, reconcile a test transaction, and record a sale exactly once.
- Reconcile refunds/chargebacks without inflating revenue.
- Restart API and worker during a queued task; verify the task resumes exactly once.
- Simulate AI provider 429/503/timeout; verify bounded fallback and eventual recovery.
- Kill switch stops new side effects while preserving evidence and queued work.

## Migration policy
- Keep the current production system serving until V2 is proven.
- Export only required business data and artifact manifests; exclude credentials, OAuth tokens, bridge secrets, and transient signed URLs.
- Preserve product IDs, offer IDs, status history, job idempotency keys, and artifact object paths where valid.
- Verify row counts, foreign keys, RLS, storage objects, and application reads before switching traffic.
- Use a reversible cutover and keep the previous deployment available for rollback.
- Do not copy the old expiring Render Postgres blindly: first establish whether it contains unique data. The active Supabase project is currently the confirmed live data plane.

## Initial product focus
Prioritize the four existing digital products already recorded in the active Supabase project. Re-audit source content and artifacts before rewriting. Do not generate duplicates or publish incomplete material. The first commercial milestone is one real Kiwify product with a verified checkout and a reconciled test sale; only then scale the catalog.