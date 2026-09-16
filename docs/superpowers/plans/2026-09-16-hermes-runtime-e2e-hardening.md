# Hermes Runtime and End-to-End Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes Pro reliably executable end-to-end from chat/topic through product generation, editable ebook and cover assets, QA, offer preparation, Hotmart integration checks, sales ingestion, analytics, and full route/UI verification without fabricated success.

**Architecture:** Preserve the existing Vercel frontend, Render API/worker, Supabase persistence/storage, Gemini AI, Redis queue where configured, Hotmart, and Telegram. Add explicit runtime readiness, persistent/recoverable job execution, document/cover asset lifecycle, editor endpoints/UI, deterministic chat commands, and integration-safe publication preparation. Every external operation is bounded, idempotent where needed, observable, and reports unavailable capabilities instead of pretending they succeeded.

**Tech Stack:** React/Vite, FastAPI, Python async workers, Pydantic Settings, Supabase Postgres/Storage, Redis, Gemini API, Hotmart APIs, Telegram, GitHub Actions, Render, Vercel.

**Spec:** `docs/superpowers/specs/2026-09-09-hermes-pro-commercial-engine-design.md`

## Global Constraints

- Keep the existing frontend/backend split.
- Keep Vercel for the frontend.
- Keep Render for API and worker deployment.
- Keep Supabase for database/storage/auth where already used.
- Keep Gemini as the AI provider already configured in the project.
- Keep Hotmart as the current sales-platform integration.
- Keep Telegram for notifications.
- Keep Redis for queued/worker work where already configured.
- Never place API keys or secrets in source code.
- Preserve `/` and `/health` API endpoints.
- Do not fabricate production metrics, publication state, sales, credentials, or completed jobs.
- Long-running generation must remain asynchronous.
- QA must block publication when required checks fail.

---

### Task 1: Establish a verified runtime contract

**Files:**
- Create: `backend/tests/test_runtime_config.py` if absent or extend it.
- Create: `backend/tests/test_health_runtime.py`.
- Modify: `backend/app/core/config.py`.
- Modify: `backend/app/main.py`.
- Modify: `backend/app/ai_gateway/factory.py` only if runtime provider selection needs correction.

**Interfaces:**
- `Settings.effective_ai_provider -> str` selects `gemini`, `openai`, `stub`, or `unconfigured` from effective environment configuration.
- `/health` remains a lightweight liveness endpoint.
- Add a sanitized readiness/status response exposing configured-state booleans only, never secret values.

- [ ] Write failing tests proving Gemini aliases, Supabase key aliases, and sanitized readiness state work.
- [ ] Run `pytest backend/tests/test_runtime_config.py backend/tests/test_health_runtime.py -v` and verify the new assertions fail before implementation.
- [ ] Implement the smallest configuration/readiness changes required; do not expose raw environment values.
- [ ] Run the focused tests again and require PASS.
- [ ] Commit with `fix: harden runtime readiness configuration`.

### Task 2: Remove queue/runtime blockers and make jobs recoverable

**Files:**
- Modify: `backend/app/queue.py`.
- Modify: `backend/app/main.py`.
- Modify: worker/runtime modules identified by the current branch's job-processing imports.
- Create/modify: backend queue and worker tests.

**Interfaces:**
- `JobQueue.enqueue(job_id: str)` persists/enqueues a job.
- `JobQueue.dequeue(timeout: int = 10)` returns a job payload or `None`.
- `recover_pending(store, queue)` restores unfinished persisted jobs without duplicating work.

- [ ] Write tests for Redis-configured queue operation, missing-Redis behavior, retry bounds, and idempotent recovery.
- [ ] Run the focused queue/worker tests and confirm failure.
- [ ] Implement a production-safe queue path using the configured Redis when available and a persistent Supabase-backed fallback when Redis is not provisioned; never rely on localhost Redis in Render.
- [ ] Ensure job transitions are persisted before/after external work and duplicate attempts are rejected or safely reused.
- [ ] Run queue/worker tests and require PASS.
- [ ] Commit with `feat: make job execution persistent and recoverable`.

### Task 3: Make the product-generation pipeline real and observable

**Files:**
- Inspect/modify: current product factory, worker, document generation, persistence/store modules on `feat/hermes-commercial-engine`.
- Create: focused tests for product-generation stages.
- Modify: schemas/routes only where required to expose stage state.

**Interfaces:**
- Product creation returns a persisted product and job ID.
- Worker stages are `queued`, `running`, `completed`, or `failed` with timestamps and sanitized errors.
- The pipeline produces editable source content plus PDF/DOCX assets and associates them with the product.

- [ ] Write tests for topic → product → job and each required stage transition.
- [ ] Run the focused tests and verify failure.
- [ ] Implement Gemini content generation with explicit prompts for title, audience, outline, chapters, and final source content; use the configured AI gateway and bounded timeouts.
- [ ] Generate PDF/DOCX from the editable source and persist assets in Supabase Storage with database metadata.
- [ ] Generate a QA report before marking the product ready.
- [ ] Run the focused tests and require PASS.
- [ ] Commit with `feat: complete asynchronous ebook production pipeline`.

### Task 4: Add ebook reading, editing, versioning, and asset access

**Files:**
- Modify: product schemas/routes/store modules.
- Create: document/version service and tests where the existing structure does not already provide one.
- Modify: `frontend/src/main.jsx` and supporting frontend modules.
- Modify: `frontend/src/style.css` as needed.

**Interfaces:**
- Read product source/content by product ID.
- Save an edited source as a new version with audit metadata.
- Regenerate document assets from a selected version.
- Download/view generated PDF/DOCX through authenticated/controlled asset URLs.

- [ ] Write backend tests for read, save-version, regenerate, and invalid-product cases.
- [ ] Run them and verify failure.
- [ ] Implement versioned editable source storage without overwriting prior versions.
- [ ] Add a Product Studio editor with readable content, save/version action, regeneration action, and explicit error/empty states.
- [ ] Add frontend tests for loading, empty, save failure, and successful version state.
- [ ] Run backend tests plus frontend tests/build and require PASS.
- [ ] Commit with `feat: add editable ebook studio and versioning`.

### Task 5: Add a dedicated cover workflow

**Files:**
- Inspect/modify existing image/cover provider modules.
- Create: cover service/tests if absent.
- Modify: product asset routes/schemas.
- Modify: frontend Product Studio cover UI.

**Interfaces:**
- Cover generation accepts product metadata and a safe visual prompt.
- Cover assets are persisted and versioned.
- A product can have one selected active cover and multiple historical cover versions.

- [ ] Write tests for generate, regenerate, select active cover, and provider failure.
- [ ] Run focused tests and verify failure.
- [ ] Implement the existing configured image-provider abstraction; if the provider is unavailable, expose a clear blocked state rather than a fake image.
- [ ] Add cover guide controls: preview, prompt/context, regenerate, select active, and associate with product.
- [ ] Run tests and frontend build.
- [ ] Commit with `feat: add versioned cover studio`.

### Task 6: Complete QA and offer preparation

**Files:**
- Modify: QA/editor services and product routes.
- Create: QA/offer tests.
- Modify: frontend Product Studio/Products views.

**Interfaces:**
- QA returns score plus findings for structure, readability, coherence, originality-risk signals, formatting, and offer clarity.
- Offer payload contains title, subtitle, description, price, currency, cover asset, document asset, and publication readiness state.

- [ ] Write tests for QA pass/fail and complete offer metadata validation.
- [ ] Run focused tests and verify failure.
- [ ] Implement deterministic validation around required metadata and block publication preparation when required assets are missing.
- [ ] Add editable offer fields and show exactly which fields/assets are missing.
- [ ] Run tests and require PASS.
- [ ] Commit with `feat: harden product QA and offer preparation`.

### Task 7: Make chat execute supported commands and use AI only when appropriate

**Files:**
- Modify: `backend/app/services/chat_commands.py`.
- Modify: `backend/app/main.py`.
- Modify: `backend/tests/test_chat_commands.py`.
- Add frontend chat tests if the current test setup supports them.

**Interfaces:**
- `handle_chat_command(message: str, store: Any, queue: Any) -> dict[str, str] | None` handles deterministic commands.
- Current-date questions must not require AI credentials.
- Product commands must create a persisted job and return its ID.
- Unsupported conversational requests fall through to the configured AI gateway.

- [ ] Fix the existing test contract mismatch by testing `handle_chat_command` directly or mocking its three-argument call signature.
- [ ] Add tests for current date, ebook creation, unsupported command fallback, and persistence failure.
- [ ] Run chat tests and verify failure where behavior is missing.
- [ ] Implement only commands backed by real routes/services; never claim an action is complete merely because a job was requested.
- [ ] Run chat tests and require PASS.
- [ ] Commit with `feat: connect Hermes chat to real operations`.

### Task 8: Complete navigation-to-API wiring and all route coverage

**Files:**
- Modify: `frontend/src/main.jsx` and frontend helpers.
- Modify: backend routes only where a guide lacks a real backing resource.
- Create: route contract/smoke tests.

**Interfaces:**
- Every primary guide maps to a real API resource: Início, Produtos, Fábrica, Radar, Vendas, Analytics, Agentes, Hermes/chat, plus health/integrations/log/control surfaces present in the UI.
- Loading, empty, and error states are explicit.

- [ ] Enumerate every route currently registered by FastAPI and every frontend API call.
- [ ] Add smoke tests covering `/`, `/health`, agents, agent execution, chat, jobs, products, radar/opportunities, events, expenses, controls/kill-switch, QA, sales, analytics, dashboard, and integration status.
- [ ] Run the route suite against a test configuration and verify failures.
- [ ] Correct mismatched paths, payloads, status handling, and UI states without embedding business rules in presentation components.
- [ ] Run the route suite and frontend build.
- [ ] Commit with `test: cover Hermes API route contracts`.

### Task 9: Verify Hotmart capability and build an honest publication adapter

**Files:**
- Inspect/modify Hotmart adapter/integration modules.
- Create: Hotmart contract tests using mocked HTTP responses.
- Modify: offer/publication status UI.

**Interfaces:**
- Adapter exposes only capabilities actually supported by the official Hotmart API/account permissions.
- Payload preparation includes title, description, price, currency, cover, document/file, and product metadata when supported.
- Sales/orders/webhook ingestion is idempotent.

- [ ] Check the current official Hotmart API documentation before implementing or asserting capabilities.
- [ ] Write contract tests for authentication, product/offer payload preparation, file/asset association where supported, sales/orders retrieval, webhook validation, timeout, and non-2xx responses.
- [ ] Run tests and verify failure.
- [ ] Implement supported capabilities with bounded timeouts and sanitized errors; mark unsupported capabilities as `not_supported` instead of simulating them.
- [ ] Verify that price, description, selected cover, and ebook asset remain linked in the local offer record before publication.
- [ ] Run contract tests and require PASS.
- [ ] Commit with `feat: harden Hotmart publication and sales adapter`.

### Task 10: Complete sales, analytics, notifications, and monitoring

**Files:**
- Modify: sales/analytics/integration services.
- Modify: frontend Vendas/Analytics/Agentes/health views.
- Create: tests for webhook idempotency, analytics empty states, and Telegram failure handling.

**Interfaces:**
- Sales metrics use persisted sales data only.
- Analytics derives explicit observations/recommendations from observed data.
- Telegram sends only configured notifications and records failure state when unavailable.

- [ ] Write tests for duplicate sales events, empty metrics, calculated revenue/order count/average ticket, and notification failure.
- [ ] Run focused tests and verify failure.
- [ ] Implement idempotent event ingestion and analytics calculations with explicit time ranges.
- [ ] Add UI states for connected, unavailable, empty, and error conditions.
- [ ] Run tests and require PASS.
- [ ] Commit with `feat: harden sales analytics and notifications`.

### Task 11: Full browser and deployment verification

**Files:**
- Modify only defects discovered by verification.
- Add/update smoke tests for confirmed regressions.

**Interfaces:**
- Production frontend loads from its configured deployment.
- Production API responds on `/` and `/health`.
- The full workflow can be exercised without fabricated state.

- [ ] Run GitHub Actions backend tests and frontend production build.
- [ ] Deploy the verified branch to the configured Render API/worker and frontend deployment target.
- [ ] Verify Render deployment status and inspect logs for startup/import/configuration errors.
- [ ] Exercise every primary guide in a real browser: Início → Produtos → Fábrica → Radar → Vendas → Analytics → Agentes → Hermes.
- [ ] Exercise the E2E path: chat command → persisted product/job → worker → Gemini → QA → PDF/DOCX → cover → editable studio → offer → Hotmart capability check → sales/analytics ingestion where credentials and sandbox/test facilities permit.
- [ ] Verify mobile viewport behavior and absence of core-workflow horizontal overflow.
- [ ] Verify no secrets, fake metrics, fake sales, or false completion claims appear in UI/API responses.
- [ ] Run final verification checks and record exact evidence before declaring completion.
- [ ] Commit only verified fixes with `fix: close end-to-end runtime verification gaps`.

## Final Acceptance Checklist

- [ ] Runtime configuration is detected without exposing secrets.
- [ ] Supabase persistence works in the deployed environment.
- [ ] Queue/worker works without an accidental localhost dependency.
- [ ] Chat current-date command works without AI; product commands create real jobs.
- [ ] Ebook generation produces editable source plus PDF/DOCX when Gemini and storage are configured.
- [ ] Ebook editor can read and save new versions.
- [ ] Cover guide can generate/select/version covers when the configured provider is available.
- [ ] QA blocks unsafe/incomplete publication states.
- [ ] Offer contains title, description, price, cover, and ebook asset before publication preparation.
- [ ] Every visible guide has a real backing API or explicit unavailable/empty state.
- [ ] All registered API routes have smoke/contract coverage.
- [ ] Hotmart integration exposes only verified supported capabilities and does not fake publication or sales.
- [ ] Sales webhooks/events are idempotent.
- [ ] Analytics uses real persisted sales data.
- [ ] Telegram reports configured events or explicit unavailable state.
- [ ] GitHub CI passes backend tests and frontend build.
- [ ] Render `/` and `/health` are live and deployment logs are clean.
- [ ] Browser verification covers desktop and mobile core workflows.
