# Hermes Pro Commercial Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Hermes Pro from the current foundation placeholder into a reliable, mobile-first commercial command center that can discover opportunities, create and review digital products, prepare Hotmart publication, track real sales, and surface operational insights.

**Architecture:** Keep the existing Vercel frontend, Render FastAPI API/worker, Supabase persistence, Gemini gateway, Hotmart, Telegram, and Redis boundaries. Build the frontend as a thin stateful client over explicit API contracts; keep long-running product generation asynchronous and represent every operation with durable job/product state rather than fabricated success. Deliver in four independently testable phases: reliable shell, product engine, commercial loop, and hardening.

**Tech Stack:** React + Vite; FastAPI + Pydantic; Python async services; Supabase/Postgres; existing Gemini gateway; existing Render worker/Redis; Hotmart and Telegram integrations already selected by the project.

**Spec:** `docs/superpowers/specs/2026-09-09-hermes-pro-commercial-engine-design.md`

## Global Constraints

- Keep Vercel/Render/Supabase/Gemini/Hotmart/Telegram/Redis; do not add unrelated providers or marketplaces.
- Secrets remain in deployment environment variables and never in source.
- Preserve `GET /` and `GET /health` as operational endpoints.
- Mobile-first; no horizontal scrolling; bottom navigation and thumb-friendly primary actions.
- Revenue, sales, integrations, and job success must use real persisted/verified data or be explicitly labeled unavailable/empty; never fabricate metrics.
- Long-running generation is asynchronous; expose queued/running/completed/failed states and structured errors.
- Use bounded transient retries and idempotent operations where external side effects exist.
- Quality gates must produce concrete findings; automatic corrections must be safe and idempotent.
- Do not claim guaranteed income; analytics should recommend experiments and optimizations.

---

## Repository Map

- `frontend/src/main.jsx` — current placeholder application entry; will become the routed command-center shell.
- `frontend/src/style.css` — current minimal visual system; will become the responsive dark-luxury design system.
- `frontend/src/` new focused modules — navigation, dashboard, products, factory, radar, sales, analytics, agents, API client, and shared UI state.
- `backend/app/main.py` — FastAPI application and route registration.
- `backend/app/schemas.py` — API request/response contracts.
- `backend/app/product_factory.py` — product pipeline and quality-gate domain logic.
- `backend/app/models/jobs.py` — job lifecycle model/store; currently in-memory and minimal.
- `backend/app/agents/*` — agent interface, registry, diagnostics, and current stubs.
- `backend/app/ai_gateway/*` — existing Gemini/provider abstraction; extend rather than replace.
- `backend/app/integrations/*` — existing integration interfaces; Hotmart/Telegram adapters must respect this boundary.
- `backend/app/workers/*` — worker-side orchestration; extend for product jobs without coupling the frontend to worker internals.
- `tests/` — add focused backend behavior tests and, if needed, a minimal frontend test setup.
- `.github/workflows/ci.yml` — preserve and extend CI coverage.

---

### Task 1: Establish isolated implementation workspace

**Files:**
- No repository files changed.

**Interfaces:**
- Starts from commit `516eee7af4cf0d68fcce8787fbaa50eb27760eaa` on `feat/hermes-foundation`.

- [ ] Ask for consent before creating an isolated git worktree, per the worktree skill.
- [ ] Create the worktree from the approved base if consented; otherwise explicitly work on the existing branch.
- [ ] Confirm the working tree is clean before implementation.

**Test:** `git status` must show the intended starting state only.

---

### Task 2: Add backend contract tests for the commercial shell

**Files:**
- Create: `tests/test_commercial_api.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces stable JSON contracts for `/api/v1/dashboard`, `/api/v1/products`, `/api/v1/jobs`, `/api/v1/radar`, `/api/v1/sales`, `/api/v1/analytics`, and `/api/v1/integrations`.
- Existing `/`, `/health`, `/api/v1/agents`, and `/api/v1/agents/run` remain backward-compatible.

- [ ] Write failing tests for empty-state dashboard, product listing, job retrieval, radar response, sales response, analytics response, and integration-health response.
- [ ] Run `pytest tests/test_commercial_api.py -q` and verify failure because the new routes/contracts do not exist.
- [ ] Add the smallest Pydantic response/request models and route implementations backed by explicit empty/unavailable state where persistence/integration data is not yet present.
- [ ] Run the focused test suite and verify all new contracts pass.
- [ ] Run existing backend tests and verify no regression.
- [ ] Commit: `feat: define commercial API contracts`.

---

### Task 3: Replace in-memory job lifecycle with explicit, testable state transitions

**Files:**
- Create: `backend/app/services/jobs.py`
- Modify: `backend/app/models/jobs.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_jobs.py`

**Interfaces:**
- `JobService.create(job_type: str, payload: dict, idempotency_key: str | None = None) -> Job`
- `JobService.get(job_id: str) -> Job`
- `JobService.transition(job_id: str, status: JobStatus, error_message: str | None = None) -> Job`
- `GET /api/v1/jobs/{job_id}` returns a stable job representation.

- [ ] Write failing tests for pending → running → completed, retrying → running, terminal failure, invalid transitions, and idempotency-key reuse.
- [ ] Run `pytest tests/test_jobs.py -q` and verify failure.
- [ ] Implement the service using the existing job model first; keep persistence behind a narrow repository boundary so Supabase can replace storage without changing API contracts.
- [ ] Add bounded retry metadata and structured error fields.
- [ ] Run focused tests and verify pass.
- [ ] Run all backend tests.
- [ ] Commit: `feat: harden job lifecycle`.

---

### Task 4: Implement product domain and factory pipeline contracts

**Files:**
- Create: `backend/app/services/products.py`
- Modify: `backend/app/product_factory.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_products.py`

**Interfaces:**
- `ProductService.create(topic: str, metadata: dict | None = None) -> Product`
- `ProductService.get(product_id: str) -> Product`
- `ProductService.list() -> list[Product]`
- `POST /api/v1/products` starts a product job and returns product/job identifiers.
- `GET /api/v1/products/{product_id}` returns stage/status/metadata.

- [ ] Write failing tests for product creation, stage ordering, status transitions, missing topic validation, and product retrieval.
- [ ] Run focused tests and verify failure.
- [ ] Implement the product model/service around the existing `PIPELINE_STAGES` and quality gate, expanding stages to match the approved spec without breaking existing semantics.
- [ ] Ensure duplicate creation with the same idempotency key does not create duplicate work.
- [ ] Run focused tests and all backend tests.
- [ ] Commit: `feat: build product pipeline domain`.

---

### Task 5: Connect the product pipeline to the existing Gemini gateway

**Files:**
- Modify: `backend/app/ai_gateway/base.py`
- Modify: `backend/app/ai_gateway/adapters.py`
- Modify: `backend/app/ai_gateway/factory.py`
- Modify: `backend/app/product_factory.py`
- Create: `tests/test_ai_product_pipeline.py`

**Interfaces:**
- Existing gateway remains the only AI-provider boundary.
- Product generation receives structured stage input and returns structured stage output/error.

- [ ] Write failing tests using a fake gateway for writer, strategist, and reviewer behavior; assert no network call occurs in tests.
- [ ] Run focused tests and verify failure.
- [ ] Implement minimal structured prompts/output parsing through the existing gateway abstraction.
- [ ] Add timeout handling and bounded transient retries at the gateway boundary.
- [ ] Ensure failed AI stages leave a failed/retryable job state rather than returning success.
- [ ] Run focused and full backend tests.
- [ ] Commit: `feat: connect product stages to ai gateway`.

---

### Task 6: Implement radar scoring and opportunity API

**Files:**
- Create: `backend/app/services/radar.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_radar.py`

**Interfaces:**
- `RadarService.score(signals: dict) -> RadarScore`
- `GET/POST /api/v1/radar` exposes demand, competition, differentiation, production difficulty, pricing potential, audience clarity, confidence, and findings.

- [ ] Write failing tests for score calculation, missing signals reducing confidence, invalid ranges, and stable deterministic output.
- [ ] Run focused tests and verify failure.
- [ ] Implement the scoring service with transparent dimensions and no unsupported market claims.
- [ ] Run focused tests and all backend tests.
- [ ] Commit: `feat: add opportunity radar`.

---

### Task 7: Add QA/review service with concrete findings

**Files:**
- Create: `backend/app/services/quality.py`
- Modify: `backend/app/product_factory.py`
- Modify: `backend/app/schemas.py`
- Create: `tests/test_quality.py`

**Interfaces:**
- `QualityService.evaluate(product: dict) -> QualityReport`
- `QualityReport` contains score, decision, dimension scores, findings, and safe-fix candidates.

- [ ] Write failing tests for passing score, revision-required score, concrete findings, and idempotent safe correction.
- [ ] Run focused tests and verify failure.
- [ ] Implement deterministic checks for structure, readability, coherence, originality-risk signals, formatting, and offer clarity; keep originality-risk phrased as a signal, not a legal guarantee.
- [ ] Run focused tests and all backend tests.
- [ ] Commit: `feat: add product quality gates`.

---

### Task 8: Implement integration-health and sales/analytics boundaries

**Files:**
- Create: `backend/app/services/integrations.py`
- Create: `backend/app/services/sales.py`
- Create: `backend/app/services/analytics.py`
- Modify: `backend/app/integrations/interfaces.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_commercial_services.py`

**Interfaces:**
- `IntegrationService.status() -> list[IntegrationStatus]`
- `SalesService.summary(range_start, range_end) -> SalesSummary`
- `AnalyticsService.insights(range_start, range_end) -> AnalyticsSummary`
- Real Hotmart data is used when the existing integration is configured; otherwise status is `unavailable`/`not_configured` rather than simulated.

- [ ] Write failing tests for unavailable integrations, real-data-only revenue, zero-sales summaries, and date-range filtering.
- [ ] Run focused tests and verify failure.
- [ ] Implement service boundaries and adapters using the existing integration interfaces.
- [ ] Ensure no API response invents revenue, orders, conversion, or product performance.
- [ ] Run focused tests and all backend tests.
- [ ] Commit: `feat: add commercial reporting boundaries`.

---

### Task 9: Wire worker orchestration for long-running product jobs

**Files:**
- Modify: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/product_worker.py`
- Modify: `backend/app/models/jobs.py`
- Create: `tests/test_product_worker.py`

**Interfaces:**
- `ProductWorker.process(job: Job) -> Job`
- Worker consumes product-generation jobs and updates stage/job state through the job service.

- [ ] Write failing tests for successful stage progression, transient retry, terminal failure, and idempotent rerun.
- [ ] Run focused tests and verify failure.
- [ ] Implement orchestration around existing worker/Redis deployment boundaries; do not make the HTTP request wait for generation.
- [ ] Run focused and full backend tests.
- [ ] Commit: `feat: orchestrate asynchronous product generation`.

---

### Task 10: Build the frontend API client and resilient state model

**Files:**
- Create: `frontend/src/lib/api.js`
- Create: `frontend/src/lib/state.js`
- Create: `frontend/src/components/StatusBadge.jsx`
- Create: `frontend/src/components/EmptyState.jsx`
- Create: `frontend/src/components/MetricCard.jsx`
- Create: `frontend/src/components/ProgressPipeline.jsx`
- Create: `frontend/src/components/IntegrationHealth.jsx`
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/state.test.js`

**Interfaces:**
- API client methods: `getDashboard`, `listProducts`, `createProduct`, `getProduct`, `getJob`, `getRadar`, `getSales`, `getAnalytics`, `getAgents`, `getIntegrations`.
- UI state explicitly distinguishes `loading`, `ready`, `empty`, `unavailable`, and `error`.

- [ ] Add the smallest frontend test runner needed for pure state/API contract tests.
- [ ] Write failing state tests for loading/empty/error/unavailable transitions.
- [ ] Run the focused frontend tests and verify failure.
- [ ] Implement the API client with configurable `VITE_API_URL`, timeout handling, JSON error normalization, and no embedded secrets.
- [ ] Implement shared status/metric/progress components.
- [ ] Run frontend tests and production build.
- [ ] Commit: `feat: add resilient frontend data layer`.

---

### Task 11: Build the mobile-first luxury command center shell

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/style.css`
- Create: `frontend/src/components/BottomNav.jsx`
- Create: `frontend/src/components/TopBar.jsx`
- Create: `frontend/src/views/Dashboard.jsx`
- Create: `frontend/src/views/Products.jsx`
- Create: `frontend/src/views/Factory.jsx`
- Create: `frontend/src/views/Radar.jsx`
- Create: `frontend/src/views/Sales.jsx`
- Create: `frontend/src/views/Analytics.jsx`
- Create: `frontend/src/views/Agents.jsx`

**Interfaces:**
- Routes/views: Início, Produtos, Fábrica, Radar, Vendas, Analytics, Agentes.
- Primary CTA: create product; secondary actions remain thumb-friendly on mobile.

- [ ] Write a render-level smoke test for navigation and critical dashboard labels if the chosen frontend test setup supports it.
- [ ] Run the smoke test and verify failure.
- [ ] Implement the shell and views using real API state plus clearly labeled empty/unavailable states.
- [ ] Implement dark-luxury visual system: near-black surfaces, warm metallic/gold accents, strong typography, restrained cards, subtle gradients/motion, and high contrast.
- [ ] Implement responsive bottom navigation, sticky mobile CTA, card-based layouts, and no horizontal overflow.
- [ ] Run frontend tests and `npm run build` from `frontend/`.
- [ ] Commit: `feat: build hermes commercial command center`.

---

### Task 12: Build Product Studio and Factory UX

**Files:**
- Modify: `frontend/src/views/Products.jsx`
- Modify: `frontend/src/views/Factory.jsx`
- Create: `frontend/src/components/ProductStudio.jsx`
- Create: `frontend/src/components/ProductCard.jsx`
- Create: `frontend/src/components/JobTimeline.jsx`
- Create: `frontend/src/components/QualityReport.jsx`
- Create: `frontend/src/components/OfferEditor.jsx`

**Interfaces:**
- Topic → opportunity → positioning → title/subtitle → outline → content → QA → cover → document → offer → publication prep.
- Product/job IDs from backend are the source of truth for progress.

- [ ] Write tests for submitting a topic, showing queued/running states, rendering failed stage errors, and rendering a quality report.
- [ ] Run tests and verify failure.
- [ ] Implement the studio flow and polling/backoff for job status without blocking the UI.
- [ ] Implement editable product metadata and offer fields.
- [ ] Implement explicit “not published” state until Hotmart confirms publication.
- [ ] Run tests and production build.
- [ ] Commit: `feat: add product studio workflow`.

---

### Task 13: Build Radar, Sales, Analytics, and Agents views

**Files:**
- Modify: `frontend/src/views/Radar.jsx`
- Modify: `frontend/src/views/Sales.jsx`
- Modify: `frontend/src/views/Analytics.jsx`
- Modify: `frontend/src/views/Agents.jsx`
- Create: `frontend/src/components/RadarScore.jsx`
- Create: `frontend/src/components/SalesSummary.jsx`
- Create: `frontend/src/components/InsightList.jsx`
- Create: `frontend/src/components/AgentRunPanel.jsx`

**Interfaces:**
- Radar displays transparent dimensions and confidence.
- Sales/Analytics display only real persisted data or explicit empty/unavailable state.
- Agents use existing registry names and run API; long jobs link to job state.

- [ ] Write tests for empty sales, unavailable Hotmart, radar missing signals, and agent error display.
- [ ] Run tests and verify failure.
- [ ] Implement views and responsive cards.
- [ ] Add actionable insight presentation without income guarantees.
- [ ] Run tests and build.
- [ ] Commit: `feat: add commercial intelligence views`.

---

### Task 14: Add Telegram event boundary

**Files:**
- Create: `backend/app/integrations/telegram.py`
- Modify: `backend/app/integrations/interfaces.py`
- Create: `backend/app/services/events.py`
- Create: `tests/test_telegram_events.py`

**Interfaces:**
- `TelegramNotifier.notify(event_type: str, payload: dict) -> DeliveryResult`
- Event types include product published, sale approved, integration error, worker failure, and goal/insight events when real data supports them.

- [ ] Write failing tests with a fake HTTP client for successful delivery, timeout, bounded retry, and missing configuration.
- [ ] Run focused tests and verify failure.
- [ ] Implement the notifier using environment-only token/chat-id configuration.
- [ ] Ensure secrets and full tokens never appear in logs or API responses.
- [ ] Run tests and all backend tests.
- [ ] Commit: `feat: add telegram operational events`.

---

### Task 15: Hardening, accessibility, and deployment verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `frontend/src/style.css` and affected components
- Modify: backend files only where verification exposes defects

**Interfaces:**
- CI validates backend tests and frontend production build.
- Deployment uses existing Vercel/Render configuration and environment variables.

- [ ] Add CI checks for backend tests and frontend build.
- [ ] Run CI locally/through GitHub Actions and verify pass.
- [ ] Verify `/` and `/health` behavior against the Render service once a deployment is available.
- [ ] Verify frontend production build and inspect the deployed page for console/runtime errors if browser automation is available.
- [ ] Test mobile widths, keyboard focus, readable contrast, disabled/loading/error states, and no horizontal overflow.
- [ ] Confirm Hotmart/Telegram are never shown as successful when unconfigured or failing.
- [ ] Update README with environment variables and operational flow without exposing secret values.
- [ ] Commit: `chore: harden hermes commercial engine`.

---

## Final Verification Checklist

- [ ] Backend tests pass.
- [ ] Frontend tests pass if configured.
- [ ] Frontend production build passes.
- [ ] `GET /` returns the API status object.
- [ ] `GET /health` returns healthy environment metadata.
- [ ] Product creation returns a real product/job identifier and asynchronous progress.
- [ ] Product failure states are visible and actionable.
- [ ] QA returns score + concrete findings.
- [ ] Radar exposes transparent scoring + confidence.
- [ ] Sales and analytics never fabricate data.
- [ ] Hotmart publication state is explicit and only marked successful on confirmation.
- [ ] Telegram notifications use deployment secrets only.
- [ ] Agents show actual registry/execution status and errors.
- [ ] Mobile UI has no horizontal scroll and primary CTA is reachable by thumb.
- [ ] CI passes.
- [ ] Deployment verification is based on actual observed output, not assumption.
