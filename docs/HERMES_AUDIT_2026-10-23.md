# Hermes operational audit — 2026-10-23

This report records observed state, not intended behavior. No secret values are included.

## Executive status

- **Radar pause: verified at the scheduler layer.** Supabase Cron jobs `hermes-autonomy-every-15m` and `hermes-opportunity-worker-5m` were unscheduled. A follow-up query of `cron.job` returned an empty list. The GitHub `main` workflow `.github/workflows/hermes-radar.yml` is manual-only and performs no API call.
- **Live API: partially available.** `/health` returns HTTP 200. `/ready` returns `degraded`: PostgreSQL is configured but the connection check fails.
- **Persistent data exists in Supabase.** Read-only inspection showed 3,435 rows in `hermes_jobs`, 6 rows in `hermes_products`, and 0 rows in `hermes_sales_events`.
- **Revenue is not proven.** No sales events were recorded in the inspected table. A proposal marked `manual_submission_required` is not a submitted bid, contract, payout, or sale.
- **No external AI call or paid product-generation run was performed during this audit.**

## Evidence and findings

### 1. Durable jobs and restart recovery

Supabase `hermes_jobs` status counts at audit time:
- `manual_submission_required`: 3,425
- `failed`: 7
- `completed`: 3
- No `pending`, `queued`, `running`, or `retrying` rows were present in that table at the queried time.
- No duplicate non-empty `idempotency_key` values were found by the audit query.
- Two jobs had a missing/empty idempotency key.

The codebase already contains `worker.main.recover_pending`, but the Render services inventory did not show a running worker service. The commercial API handles product jobs with FastAPI background tasks, which are not durable by themselves across a process restart.

**Change merged:** startup recovery for durable `product_generation` jobs, plus a process-local duplicate-execution guard. Regression tests cover recovering pending/retrying/running product jobs and ignoring terminal or unrelated jobs. The product pipeline test uses fake AI/storage adapters to exercise strategy → writing → QA → cover/PDF/DOCX generation → upload contract without real external API calls.

**Limit:** live restart recovery remains unproven until the live PostgreSQL connection is restored and a controlled disposable job can be interrupted and recovered.

### 2. Product generation and files

Supabase `hermes_products` showed:
- 6 total products
- 2 marked `completed` but with empty `artifacts`
- 4 marked `failed`
- No artifact URLs in the inspected product rows.

The repository's artifact builder creates PNG cover, DOCX, and PDF files. CI now tests file signatures and exercises the product worker with mocked AI and storage. This verifies local artifact generation and pipeline logic, **not** successful upload to live Supabase Storage or a sellable product being published.

### 3. Live dependencies and credential status

Live `/ready` response for `hermes-pro-api-commercial`:
- PostgreSQL: configured, **connection failed**
- Gemini: key configured; actual key validity/quota was not tested
- Redis: URL configured; actual connection was not tested by `/ready`
- Hotmart: not configured
- Telegram: not configured
- Canva: not configured
- Freelancer.com: access token not configured according to the integrations endpoint

No secret values were read into this report.

### 4. Deployment and service drift

Observed Render services include:
- `hermes-pro-api-commercial`: Ohio, branch `feat/hermes-commercial-engine`
- `hermes-pro-api-virginia`: Virginia, branch `feat/hermes-commercial-engine`; live readiness showed missing `DATABASE_URL` and Gemini key
- `hermes-pro-api-feature`: Ohio, branch `feat/real-infrastructure`
- `hermes-pro-api`: Ohio, branch `main`; `/ready` returned 404 on the older deployment
- `hermes-pro-command-center`: static site on `feat/hermes-autonomous-hardening`
- `hermes-pro-redis`: Redis/Key Value in Ohio; persistence mode is off

GitHub had 85 branches at audit time. This is evidence of substantial branch drift; branches must not be bulk-deleted without comparing unique commits, open PRs, and deployed references.

The database `hermes-pro-db` is a Free PostgreSQL instance in Virginia, currently reported available but with an expiration date of **2026-11-13**. The live commercial API is in Ohio and reports a PostgreSQL connection failure. Render's remote SQL tool cannot query the database because its external connection is blocked by the database IP allowlist; the allowlist was not loosened as a workaround.

**Blocking item:** select one canonical API/database region and repair the configured connection path. Then validate database connectivity from the actual service. Do not assume that a configured URL means a working connection.

### 5. Commercial proof and profitability

The inspected `hermes_sales_events` table had zero rows. This means there is no evidence in that ledger of a completed sale/payment. Proposal drafts and `manual_submission_required` tasks do not count as revenue.

The safe first commercial acceptance test should be one approved service/product with:
1. explicit scope and price;
2. generated files that pass format checks;
3. real storage URLs that can be fetched;
4. human review before any external submission/publication;
5. a recorded payment event before revenue is counted;
6. net-profit calculation after platform fees, AI, storage/hosting, refunds, and applicable taxes.

The opportunity Radar remains paused and must not be resumed without the owner's request.

## Change records

- PR #66: fixed the PostgreSQL update call contract and added a persistence regression test; merged.
- PR #68: added product startup recovery, duplicate-run guard, and offline pipeline/artifact tests; merged.
- PR #65: architecture proposal; it does not itself mean every architecture component is implemented.

## Next safe sequence

1. Repair the Render API ↔ PostgreSQL connection without exposing or replacing secrets.
2. Resolve service/region drift and record one canonical production API.
3. Confirm Redis connectivity and whether queue persistence is acceptable; current Redis persistence mode is off.
4. Run a disposable DB create/read/update/restart test.
5. Run one controlled product generation using the configured AI provider only after checking usage/cost, then verify uploaded files with real HTTP fetches.
6. Add integration expiry/rotation checks that report credential *presence and health* without logging values; test each provider only through a safe authenticated probe.
7. Execute one reviewed commercial delivery and record actual payment before declaring revenue.
8. Review unused branches and services only after mapping their unique commits and production dependencies.
