# Hermes Autonomous Commerce Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing Hermes product factory into a persistent, measurable autonomous commerce engine that discovers opportunities, scores products/services, executes approved work, enforces QA/budget controls, and exposes the state through one command center.

**Architecture:** Keep the existing FastAPI + Supabase + Render worker + Vercel frontend architecture. Add bounded domain services for opportunities, services, controls, economics, agents, and channel adapters instead of turning `main.py` into a monolith. Persist every autonomous decision and job so restarts cannot lose state; keep publishing behind explicit channel capabilities and QA gates.

**Tech Stack:** Python/FastAPI, Pydantic, Supabase Postgres/Storage, existing Redis-or-local queue, Gemini through the existing AI gateway, React/Vite frontend, GitHub Actions, Render, Vercel.

**Spec:** User-approved Hermes Autonomous Commerce Engine architecture supplied in the conversation and the existing commercial-engine design in `docs/superpowers/specs/2026-09-09-hermes-pro-commercial-engine-design.md`.

## Global Constraints

- Revenue target R$900/day is an optimization target, never a guarantee.
- Operating metric is revenue minus AI, infrastructure, advertising, and other recorded costs.
- Missing market/sales signals reduce confidence; Hermes must never fabricate demand, sales, costs, or integration success.
- Products and services are separate opportunity types but share discovery, scoring, job, QA, economics, and analytics primitives.
- No publication is allowed when mandatory QA fails.
- Every externally mutating operation must be idempotent.
- Work must be performed on `feat/hermes-autonomous-commerce-engine`; do not modify protected/default branches directly.
- Use TDD for production behavior changes: write a failing test, verify RED, implement minimally, verify GREEN, then refactor.

---

### Task 1: Establish the domain contracts and tests

**Files:**
- Create: `backend/app/domain/opportunities.py`
- Create: `backend/app/domain/economics.py`
- Create: `backend/app/domain/controls.py`
- Create: `backend/tests/test_opportunities.py`
- Create: `backend/tests/test_economics.py`
- Create: `backend/tests/test_controls.py`

**Interfaces:**
- `score_opportunity(signals: dict) -> dict` returns `score`, `confidence`, normalized dimensions, and findings.
- `estimate_profit(revenue: float, ai_cost: float, infra_cost: float, ads_cost: float, other_cost: float) -> float` returns the operating-profit estimate rounded to cents.
- `control_allows(action: str, settings: dict) -> tuple[bool, str]` enforces global kill switch, per-domain pauses, and daily budget thresholds.

- [ ] Write a failing opportunity-score test covering demand, margin, ease, conversion probability, capacity, competition, cost, and risk.
- [ ] Run `pytest backend/tests/test_opportunities.py -v` and confirm the missing implementation failure.
- [ ] Implement the smallest deterministic score function with confidence based on supplied signal completeness.
- [ ] Run the test again and confirm PASS.
- [ ] Write a failing economics test proving profit equals revenue minus all five cost categories.
- [ ] Run the economics test and confirm RED.
- [ ] Implement `estimate_profit` with no hidden assumptions.
- [ ] Run the economics test and confirm GREEN.
- [ ] Write failing control tests for global pause, domain pause, budget exceeded, and allowed action.
- [ ] Run the control tests and confirm RED.
- [ ] Implement the control evaluator.
- [ ] Run all three test files and confirm GREEN.
- [ ] Commit `feat: add commerce scoring economics and controls`.

### Task 2: Persist opportunities, services, costs, controls, and events

**Files:**
- Create: `backend/supabase/migrations/20260915_autonomous_commerce.sql`
- Modify: `backend/app/db/supabase.py`
- Create: `backend/app/services/opportunities.py`
- Create: `backend/app/services/controls.py`
- Create: `backend/tests/test_persistence_contracts.py`

**Interfaces:**
- Tables: `hermes_opportunities`, `hermes_opportunity_scores`, `hermes_services`, `hermes_expenses`, `hermes_settings`, `hermes_events`, `hermes_agent_runs`.
- `OpportunityService.create(...)`, `list(...)`, `get(...)`, `score(...)` persist opportunity state and scores.
- `ControlService.get()`, `update(...)`, `allows(...)` persist kill-switch, pause, and budget state.

- [ ] Write failing persistence-contract tests for opportunity idempotency and control defaults.
- [ ] Verify RED.
- [ ] Add the SQL migration with UUID keys, timestamps, JSONB metadata, indexes, and unique idempotency keys; enable RLS and deny public writes by default.
- [ ] Add only the Supabase REST operations required by the new services.
- [ ] Implement `OpportunityService` and `ControlService` against the existing `SupabaseREST` abstraction.
- [ ] Run persistence-contract tests and confirm GREEN.
- [ ] Commit `feat: persist autonomous commerce state`.

### Task 3: Add the autonomous opportunity and service APIs

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/services/service_opportunities.py`
- Create: `backend/tests/test_api_contracts.py`

**Interfaces:**
- `POST /api/v1/opportunities` creates a product/service opportunity.
- `GET /api/v1/opportunities` returns ranked opportunities.
- `POST /api/v1/opportunities/{id}/score` recomputes a score.
- `GET /api/v1/services` lists service opportunities and their execution state.
- `POST /api/v1/services` creates a service execution candidate.
- `GET /api/v1/controls` returns persisted control state.
- `PUT /api/v1/controls` updates control state.
- `POST /api/v1/events` records an operational event.

- [ ] Write failing API tests for creation, ranking, control retrieval, and event recording.
- [ ] Verify RED.
- [ ] Add Pydantic request/response schemas with explicit enums for opportunity type and service state.
- [ ] Implement endpoints using domain services; do not add business logic directly to route handlers.
- [ ] Run API contract tests and confirm GREEN.
- [ ] Commit `feat: expose autonomous commerce APIs`.

### Task 4: Turn agents into executable bounded contracts

**Files:**
- Modify: `backend/app/agents/base.py`
- Modify: `backend/app/agents/registry.py`
- Create: `backend/app/agents/contracts.py`
- Create: `backend/app/agents/core.py`
- Create: `backend/app/agents/opportunity.py`
- Create: `backend/app/agents/product.py`
- Create: `backend/app/agents/service.py`
- Create: `backend/app/agents/qa.py`
- Create: `backend/app/agents/optimizer.py`
- Create: `backend/app/agents/guardian.py`
- Create: `backend/tests/test_agents.py`

**Interfaces:**
- Each agent exposes `name`, `capabilities`, and async `run(input: dict) -> dict`.
- Agent runs return job/run IDs and never claim an external side effect unless its adapter reports success.
- Guardian is the final control check before publish/spend actions.

- [ ] Write failing tests for agent registration, capability boundaries, and guardian denial when controls block an action.
- [ ] Verify RED.
- [ ] Implement contracts and bounded agents by composing existing services and AI gateway calls.
- [ ] Replace generic pass-through registrations for the autonomous agents while retaining diagnostics.
- [ ] Run agent tests and confirm GREEN.
- [ ] Commit `feat: add executable autonomous agents`.

### Task 5: Extend the worker state machine and autonomous loop

**Files:**
- Modify: `backend/app/queue.py`
- Modify: `backend/app/worker_runtime.py`
- Modify: `worker/main.py`
- Create: `backend/app/services/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Job states: `PENDING`, `RUNNING`, `QA`, `APPROVED`, `PUBLISHED`, `MONITORING`, `COMPLETED`, `FAILED`, `RETRYING`, `BLOCKED`, `CANCELLED`.
- `Orchestrator.run_cycle()` discovers runnable opportunities, applies controls, creates jobs, and records events.
- Existing ebook factory remains a product execution capability rather than the whole system.

- [ ] Write failing tests for state transitions, idempotent retry, blocked jobs, and kill-switch behavior.
- [ ] Verify RED.
- [ ] Implement transition validation and orchestrator cycle.
- [ ] Preserve the existing successful PDF/DOCX/cover pipeline and attach it to product jobs.
- [ ] Run worker/orchestrator tests and confirm GREEN.
- [ ] Commit `feat: add autonomous commerce orchestration`.

### Task 6: Add channel-adapter boundaries and Hotmart readiness

**Files:**
- Modify: `backend/app/integrations/interfaces.py`
- Create: `backend/app/integrations/channel_adapter.py`
- Create: `backend/app/integrations/hotmart.py`
- Create: `backend/tests/test_channel_adapters.py`

**Interfaces:**
- Adapter contract: `create_product`, `upload_file`, `set_price`, `publish`, `get_product`, `get_sales`, `get_orders`, `get_status`, `receive_webhook`.
- Hotmart adapter must distinguish configured, authenticated, unavailable, and unsupported operations.

- [ ] Write failing adapter contract tests for capability reporting and idempotent publication.
- [ ] Verify RED.
- [ ] Implement the generic adapter protocol and a Hotmart implementation using official API endpoints only.
- [ ] Do not scrape or automate prohibited marketplace interfaces.
- [ ] Run adapter tests and confirm GREEN.
- [ ] Commit `feat: add channel adapter boundary`.

### Task 7: Add Telegram notifications and economics/analytics integration

**Files:**
- Create: `backend/app/integrations/telegram.py`
- Modify: `backend/app/services/analytics.py`
- Modify: `backend/app/services/sales.py`
- Create: `backend/tests/test_notifications.py`
- Create: `backend/tests/test_profit_analytics.py`

**Interfaces:**
- `TelegramNotifier.send(event: dict) -> dict` reports real delivery status only.
- Analytics exposes revenue, costs, estimated operating profit, ROI, conversion, and confidence.

- [ ] Write failing tests for notification-disabled behavior and profit calculation from persisted expenses.
- [ ] Verify RED.
- [ ] Implement Telegram notification adapter and analytics aggregation.
- [ ] Run notification and analytics tests and confirm GREEN.
- [ ] Commit `feat: add notifications and profit analytics`.

### Task 8: Upgrade the command interface from chat to actions

**Files:**
- Modify: `backend/app/services/commercial.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_commands.py`

**Interfaces:**
- Commands include: find opportunities, produce selected opportunities, find compatible services, pause operations, resume operations, explain sales changes, set budgets, and create a product.
- `parse_chat_command(message)` returns an explicit action and validated parameters.
- Chat executes real internal actions when a deterministic command is recognized; otherwise it uses the AI gateway for explanation only.

- [ ] Write failing parser tests for all command families and the existing price command.
- [ ] Verify RED.
- [ ] Fix the existing price-regex ambiguity and add the new action grammar.
- [ ] Route recognized actions to services and return operation IDs/results.
- [ ] Run command tests and confirm GREEN.
- [ ] Commit `feat: make Hermes chat operational`.

### Task 9: Build the Command Center for the autonomous engine

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/workspace.css`
- Create: `frontend/src/api.js`
- Create: `frontend/src/components/OpportunityList.jsx`
- Create: `frontend/src/components/ServiceList.jsx`
- Create: `frontend/src/components/ControlPanel.jsx`
- Create: `frontend/src/components/HealthPanel.jsx`

**Interfaces:**
- Sections: Início, Produtos, Fábrica, Radar, Serviços, Vendas, Analytics, Agentes, Logs, Controles.
- All panels consume the API; no fake sales/opportunity values are hardcoded.
- Control actions visibly show success/failure and current persisted state.

- [ ] Write frontend tests for opportunity rendering and control actions using the existing frontend test setup; if no test runner exists, add Vitest and one deterministic component test before implementation.
- [ ] Verify RED.
- [ ] Extract API calls into `api.js` and implement the new sections using existing visual conventions.
- [ ] Add operating-profit and cost cards that display `null`/"sem dados" when real data is absent.
- [ ] Run frontend tests and build; confirm GREEN.
- [ ] Commit `feat: add autonomous command center views`.

### Task 10: Documentation, deployment configuration, and verification

**Files:**
- Create: `docs/superpowers/specs/2026-09-15-hermes-autonomous-commerce-engine-design.md`
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml`

- [ ] Write the definitive architecture spec covering products, services, scoring, QA, controls, jobs, channels, economics, and prohibited automation.
- [ ] Update README from ebook-factory language to Autonomous Commerce Engine language and document the first revenue path as product preparation + authorized Hotmart publication.
- [ ] Add non-secret environment variable documentation for AI provider, controls, Hotmart, Telegram, Supabase, and CORS.
- [ ] Ensure CI runs backend tests and frontend build/tests.
- [ ] Run the complete backend test suite and frontend build/tests.
- [ ] Inspect GitHub Actions results for the branch.
- [ ] Inspect Render deployment and smoke-test `/`, `/health`, `/api/v1/dashboard`, `/api/v1/opportunities`, `/api/v1/controls`, and `/api/v1/products`.
- [ ] Verify the frontend can load the API and that a product creation reaches a real persisted job without fabricated sales.
- [ ] Commit `docs: document autonomous commerce engine`.

### Task 11: Review and handoff

**Files:**
- No production files unless review finds a defect.

- [ ] Compare the branch against `feat/hermes-autonomous-hardening` and inspect all changed files.
- [ ] Run verification again after any review fixes.
- [ ] Open a draft PR into `feat/hermes-autonomous-hardening` with explicit verification evidence and known external prerequisites.
- [ ] Do not merge automatically.
