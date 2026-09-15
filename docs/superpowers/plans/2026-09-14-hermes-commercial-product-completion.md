# Hermes Commercial Product Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing ebook factory into a complete, inspectable, commercially-ready product pipeline with real content, assets, offer metadata, price research, storage references, and actionable UI/chat controls.

**Architecture:** Keep the existing FastAPI + Supabase + worker architecture. Extend the persisted product metadata and APIs so every generated product has content, assets, commercial metadata, and explicit publication readiness. Extend the existing React UI so the product workspace exposes the complete package and the Hermes chat can trigger supported product actions without pretending external publication or sales occurred.

**Tech Stack:** Python/FastAPI, Supabase REST/storage, existing AI gateway, ReportLab, python-docx, Pollinations image provider, React/Vite.

**Spec:** User-approved commercial product design in the conversation on 2026-09-14.

## Global Constraints

- Never fabricate market prices, sales, publication status, integrations, or external results.
- A product is "ready_to_sell" only when required content and assets exist and quality is approved.
- Store durable asset paths/URLs in Supabase metadata so the publication adapter can consume them later.
- Price recommendations must be labeled as market references/recommendations, not guarantees.
- Preserve existing API contracts where possible and keep explicit loading/error states in the UI.
- Use tests before production behavior changes.

---

### Task 1: Persist complete commercial metadata

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/persistence.py`
- Test: `backend/tests/test_commercial_product.py`

**Interfaces:**
- Add a typed commercial metadata shape or equivalent validation for title/subtitle/description/audience/category/keywords/price/price_basis/publication_status.
- Keep existing `ProductResponse` compatible while exposing the new metadata.

- [ ] Write failing tests for required commercial metadata and ready-to-sell gating.
- [ ] Run the focused tests and verify the new assertions fail for the current implementation.
- [ ] Implement the smallest persistence/schema changes.
- [ ] Run focused tests and the existing backend suite.
- [ ] Commit the task.

### Task 2: Generate the complete commercial package

**Files:**
- Modify: `worker/main.py`
- Test: `backend/tests/test_commercial_product.py`

**Interfaces:**
- Extend `process_product()` so the AI creates commercial metadata after review and before final completion.
- Generate and persist description, short description, audience, category, keywords, subtitle, suggested price, and price rationale.
- Keep PDF/DOCX/cover generation and persist their paths/URLs.

- [ ] Write failing tests covering the commercial metadata structure and final state.
- [ ] Run focused tests to confirm failure.
- [ ] Implement generation and metadata persistence.
- [ ] Run focused tests and backend tests.
- [ ] Commit the task.

### Task 3: Add evidence-based price research

**Files:**
- Modify: `backend/app/services/radar.py` or create a focused pricing service
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_pricing.py`

**Interfaces:**
- Provide a price recommendation endpoint/service that accepts topic/category and returns comparable observations when real web data is available, plus a confidence/evidence field.
- Never present invented comparables as market data.

- [ ] Write failing tests for recommendation output and missing-evidence behavior.
- [ ] Run tests and confirm failure.
- [ ] Implement evidence-aware recommendation logic.
- [ ] Run tests and backend suite.
- [ ] Commit the task.

### Task 4: Make product workspace fully inspectable

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/workspace.css`
- Test: existing frontend build/type checks

**Interfaces:**
- Product workspace must show title/subtitle, description, audience, category, keywords, suggested price, price rationale, quality, full text, cover, PDF, DOCX, storage paths, and publication readiness.
- Add safe UI actions for editing/regenerating metadata and assets where backend endpoints exist.

- [ ] Add frontend tests/checks for rendering commercial metadata and asset states.
- [ ] Run checks and confirm the new behavior is absent/failing.
- [ ] Implement the workspace changes.
- [ ] Run `npm run build` and any available frontend checks.
- [ ] Commit the task.

### Task 5: Connect Hermes chat to real product operations

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Modify: `frontend/src/main.jsx`
- Test: `backend/tests/test_chat_actions.py`

**Interfaces:**
- Support deterministic commands for product lookup, status, asset access, price changes, and regeneration requests.
- Natural-language AI responses remain available, but action execution must be explicit and truthful.
- External publication remains separate and must report the actual adapter state.

- [ ] Write failing tests for at least status, price update, and asset lookup actions.
- [ ] Run tests and confirm failure.
- [ ] Implement action routing.
- [ ] Run backend and frontend tests/build.
- [ ] Commit the task.

### Task 6: End-to-end verification and deployment

**Files:**
- No source changes unless verification exposes a defect.

- [ ] Verify the production API health and current deployment.
- [ ] Create a fresh test product through the live API/UI.
- [ ] Verify job execution reaches completed or review-required with truthful status.
- [ ] Verify PDF, DOCX, and cover URLs are persisted and accessible.
- [ ] Verify the UI exposes the generated text and commercial metadata.
- [ ] Verify chat actions against the fresh product.
- [ ] Verify no fabricated publication/sales claims.
- [ ] Only then report the system as verified.
