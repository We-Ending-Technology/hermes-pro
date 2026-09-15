# Hermes Autonomous Commerce Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Hermes Pro into a persistent, testable opportunity-to-revenue operating system that can discover, score, produce, QA, prepare/publish through legitimate channels, measure costs/results, and continuously optimize products and services from one command center.

**Architecture:** Keep the existing FastAPI + Supabase + Render + Vercel foundation and extend it with bounded domain services for opportunities, agents, controls, costs, services, and channel adapters. Use persistent Supabase state as the source of truth, a durable job lifecycle with idempotency/retries, and real connector/API capabilities only where supported and permitted.

**Tech Stack:** Python/FastAPI, Supabase Postgres/Storage, Render, Vercel, Gemini via backend API, existing PDF/DOCX/cover pipeline, GitHub CI, optional Telegram/Hotmart/analytics connectors.

**Spec:** `docs/superpowers/specs/2026-09-15-hermes-autonomous-commerce-engine-design.md`

## Global Constraints

- Revenue, cost, profit, sales, and publication state must only be reported from real persisted evidence.
- R$900/day is an optimization target, never a guaranteed outcome.
- Missing market signals reduce confidence; they are never fabricated.
- Freelance/channel automation must use legitimate official mechanisms and respect platform terms.
- QA failure blocks publication/delivery.
- Every repeatable job needs an idempotency key and bounded retry behavior.
- Kill switches and budget limits must be enforceable before expensive/external actions.
- Human approval remains configurable for risky external actions.
- Gemini remains an API integration; no fake Gemini connector is required.

---

### Task 1: Lock the architecture specification

**Files:**
- Create: `docs/superpowers/specs/2026-09-15-hermes-autonomous-commerce-engine-design.md`
- Modify: `README.md`

**Interfaces:**
- Produces the domain contracts consumed by Tasks 2-9.

- [ ] **Step 1: Write the failing documentation acceptance checklist**

Create a checklist in the spec covering opportunity scoring, products/services, agents, jobs, QA, costs/profit, controls, channels, dashboard, and 24/7 recovery.

- [ ] **Step 2: Verify the checklist is incomplete against the supplied architecture**

Run a manual comparison against the uploaded architecture and record any missing domain requirement before implementation.

- [ ] **Step 3: Write the complete specification**

Document the exact domain entities, state transitions, agent contracts, score dimensions, safety/approval controls, and real-data rules.

- [ ] **Step 4: Verify the spec covers all required architecture sections**

Confirm every requested subsystem has an owning module and persisted state.

- [ ] **Step 5: Commit**

`git add docs/superpowers/specs/2026-09-15-hermes-autonomous-commerce-engine-design.md README.md && git commit -m "docs: define autonomous commerce engine"`

---

### Task 2: Opportunity Engine and economic scoring

**Files:**
- Create: `backend/app/services/opportunities.py`
- Create: `backend/tests/test_opportunities.py`
- Modify: `backend/app/schemas.py`

**Interfaces:**
- `OpportunityInput` -> `OpportunityScore`
- `OpportunityEngine.score(input) -> OpportunityScore`
- `OpportunityEngine.decide(score, policy) -> Decision`

- [ ] **Step 1: Write failing score tests**

Test that stronger demand/margin/ease/conversion increases score, competition/cost/risk decrease score, and absent evidence lowers confidence rather than creating values.

- [ ] **Step 2: Run `pytest backend/tests/test_opportunities.py -v` and verify RED**

Expected: import/function failures because the engine does not yet exist.

- [ ] **Step 3: Implement the minimal deterministic scoring engine**

Use normalized 0-100 dimensions and return score, confidence, findings, and recommended action.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Expected: all opportunity tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/services/opportunities.py backend/app/schemas.py backend/tests/test_opportunities.py && git commit -m "feat: add opportunity scoring engine"`

---

### Task 3: Persistent domain state for opportunities, costs, controls, and experiments

**Files:**
- Create: `backend/app/services/commerce_store.py`
- Create: `backend/migrations/20260915_autonomous_commerce.sql`
- Create: `backend/tests/test_commerce_store.py`
- Modify: `backend/app/db/supabase.py`

**Interfaces:**
- `CommerceStore.create_opportunity`, `list_opportunities`, `get_opportunity`
- `CommerceStore.record_expense`, `list_expenses`
- `CommerceStore.record_event`, `list_events`
- `CommerceStore.get_setting`, `set_setting`
- `CommerceStore.create_experiment`, `list_experiments`

- [ ] **Step 1: Write failing persistence contract tests**

Test payload normalization, idempotent opportunity creation, expense totals, event creation, and control settings.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing store methods/schema.

- [ ] **Step 3: Implement the migration and store methods**

Add `hermes_opportunities`, `hermes_expenses`, `hermes_events`, `hermes_experiments`, `hermes_settings`, `hermes_agent_runs`, and `hermes_system_health` with timestamps, indexes, RLS, and unique idempotency keys where applicable.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: persistence contract tests pass against the local store abstraction.

- [ ] **Step 5: Commit**

`git add backend/migrations/20260915_autonomous_commerce.sql backend/app/services/commerce_store.py backend/app/db/supabase.py backend/tests/test_commerce_store.py && git commit -m "feat: persist autonomous commerce state"`

---

### Task 4: Agent contracts and orchestrator

**Files:**
- Create: `backend/app/agents/contracts.py`
- Create: `backend/app/agents/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`
- Modify: `backend/app/agents/registry.py`

**Interfaces:**
- `AgentContext`, `AgentResult`, `AgentCapability`
- `AgentOrchestrator.run(agent_name, context) -> AgentResult`
- registry exposes real bounded agents without granting unrestricted side effects.

- [ ] **Step 1: Write failing orchestration tests**

Test successful dispatch, unknown-agent rejection, permission rejection, and run metadata creation.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing contract/orchestrator behavior.

- [ ] **Step 3: Implement bounded contracts and dispatch**

Represent Radar, Intelligence, Product, Service, Design, Document, QA, Marketplace, Sales, Analytics, Optimizer, Guardian, and Watchtower as named capabilities; keep side effects behind services/adapters.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all orchestration tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/agents backend/tests/test_orchestrator.py && git commit -m "feat: add bounded agent orchestrator"`

---

### Task 5: Operational controls, budget guard, and kill switches

**Files:**
- Create: `backend/app/services/controls.py`
- Create: `backend/tests/test_controls.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- `ControlService.is_allowed(action, estimated_cost) -> ControlDecision`
- `ControlService.set_kill_switch(name, enabled)`
- `ControlService.get_status() -> ControlStatus`

- [ ] **Step 1: Write failing control tests**

Test blocked publishing, blocked spend over daily budget, global stop, and allowed low-cost work.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing control service.

- [ ] **Step 3: Implement controls and API endpoints**

Expose status and mutation endpoints while enforcing controls before external publishing, paid AI, or advertising actions.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all control tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/services/controls.py backend/app/main.py backend/tests/test_controls.py && git commit -m "feat: add commerce controls and kill switches"`

---

### Task 6: Product/service opportunity workflows

**Files:**
- Create: `backend/app/services/service_opportunities.py`
- Create: `backend/tests/test_service_opportunities.py`
- Modify: `backend/app/services/radar.py`
- Modify: `backend/app/commercial.py`

**Interfaces:**
- `discover_product_opportunities(...)`
- `classify_service_opportunity(...)`
- `build_product_brief(...)`
- `build_service_brief(...)`

- [ ] **Step 1: Write failing workflow tests**

Test product types, service compatibility scoring, and proposal readiness without claiming execution or publication.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing workflow functions.

- [ ] **Step 3: Implement deterministic workflow normalization**

Connect opportunity scores to product factory metadata and service briefs; keep external execution separate from discovery.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all workflow tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/services/service_opportunities.py backend/app/services/radar.py backend/app/commercial.py backend/tests/test_service_opportunities.py && git commit -m "feat: add product and service opportunity workflows"`

---

### Task 7: Real job lifecycle, recovery, events, and optimization loop

**Files:**
- Create: `backend/app/services/lifecycle.py`
- Create: `backend/tests/test_lifecycle.py`
- Modify: `backend/app/queue.py`
- Modify: `backend/app/worker_runtime.py`
- Modify: `backend/worker/main.py`

**Interfaces:**
- `transition_job(job, target_state)`
- `retry_policy(attempt, max_attempts)`
- `recover_stale_jobs(...)`
- `calculate_operating_profit(...)`

- [ ] **Step 1: Write failing lifecycle tests**

Test legal state transitions, retry limits, stale recovery, and profit calculation from revenue minus recorded costs.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing lifecycle behavior.

- [ ] **Step 3: Implement lifecycle guards and recovery**

Persist every transition/event, use exponential backoff with bounded attempts, and calculate operating profit only from persisted data.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all lifecycle tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/services/lifecycle.py backend/app/queue.py backend/app/worker_runtime.py backend/worker/main.py backend/tests/test_lifecycle.py && git commit -m "feat: harden autonomous job lifecycle"`

---

### Task 8: Channel adapters and real integration boundaries

**Files:**
- Create: `backend/app/channels/base.py`
- Create: `backend/app/channels/hotmart.py`
- Create: `backend/app/channels/telegram.py`
- Create: `backend/tests/test_channels.py`
- Modify: `backend/app/services/integrations.py`

**Interfaces:**
- `ChannelAdapter.create_product`, `upload_file`, `set_price`, `publish`, `get_product`, `get_sales`, `get_orders`, `get_status`, `receive_webhook`
- Hotmart only reports published/sold after confirmed API/webhook evidence.
- Telegram only reports sent after a successful API response.

- [ ] **Step 1: Write failing adapter contract tests**

Test capability reporting and that unconfigured channels return explicit unavailable/blocked states rather than success.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: missing adapter classes.

- [ ] **Step 3: Implement adapters and capability checks**

Keep credentials in environment configuration and never store secrets in source. Implement only documented official mechanisms.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all channel tests pass.

- [ ] **Step 5: Commit**

`git add backend/app/channels backend/app/services/integrations.py backend/tests/test_channels.py && git commit -m "feat: add channel adapter boundaries"`

---

### Task 9: Command Center expansion

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/workspace.css`
- Create: `frontend/src/commerceApi.js`
- Create: `frontend/src/commerceApi.test.js`

**Interfaces:**
- Frontend consumes `/api/v1/opportunities`, `/api/v1/services`, `/api/v1/controls`, `/api/v1/events`, `/api/v1/health`, `/api/v1/analytics`.

- [ ] **Step 1: Write failing API contract tests**

Test API URL normalization and response handling for the new command-center resources.

- [ ] **Step 2: Run the focused frontend tests and verify RED**

Expected: missing commerce API helpers.

- [ ] **Step 3: Implement the new dashboard sections**

Add Radar, Serviços, Controles/kill switches, costs/profit, events, health, and agent status while preserving the existing product workspace.

- [ ] **Step 4: Run frontend tests/build and verify GREEN**

Expected: tests and `npm run build` pass.

- [ ] **Step 5: Commit**

`git add frontend/src && git commit -m "feat: expand autonomous command center"`

---

### Task 10: Integration, CI, deployment, and commercial smoke test

**Files:**
- Modify: `.github/workflows/*` only where required by failing CI
- Modify: `README.md`
- Create: `docs/runbooks/autonomous-commerce.md`

**Interfaces:**
- End-to-end path: radar -> opportunity -> product job -> QA -> ready-to-sell -> channel readiness -> cost/result event -> analytics.

- [ ] **Step 1: Run the complete backend test suite**

Run `pytest backend/tests -v` and record failures without bypassing them.

- [ ] **Step 2: Run the complete frontend test/build suite**

Run the configured frontend test command and `npm run build`.

- [ ] **Step 3: Fix only failures with tests first**

For every bug, add a failing regression test before changing production code.

- [ ] **Step 4: Push branch and inspect CI**

Wait for required GitHub checks; do not claim success from local tests alone.

- [ ] **Step 5: Deploy to Render/Vercel through the existing connected deployment path**

Confirm the deployed API, frontend, database connectivity, worker health, and configured integrations.

- [ ] **Step 6: Run production smoke tests**

Verify `/`, `/health`, dashboard, opportunity creation, product creation, job progression, and no false sales/publication claims.

- [ ] **Step 7: Commit final runbook/verification evidence**

`git add README.md docs/runbooks/autonomous-commerce.md && git commit -m "docs: add autonomous commerce runbook"`

---

## Verification Gate

Before calling the implementation complete:

1. All backend tests pass.
2. All frontend tests/build pass.
3. CI required checks are green.
4. Deployed API and frontend are reachable.
5. Supabase migration is applied and queried successfully.
6. A product job completes through QA using real AI/storage when configured.
7. No endpoint reports a sale, publication, or profit without persisted evidence.
8. Kill switch blocks an external action in a live smoke test.
9. Connector health distinguishes configured, unavailable, and blocked states.
10. Final report separates **implemented**, **configured**, and **not yet credentialed/verified** capabilities.
