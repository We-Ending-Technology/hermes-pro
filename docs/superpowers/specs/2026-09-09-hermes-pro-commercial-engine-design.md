# Hermes Pro Commercial Engine — Design Specification

**Date:** 2026-09-09  
**Branch:** `feat/hermes-foundation`

## Goal

Transform Hermes Pro from a foundation/placeholder interface into a reliable, mobile-first command center for discovering, creating, reviewing, publishing, selling, and optimizing digital products, while preserving the current platform stack and avoiding unsupported promises of guaranteed income.

## Product Positioning

Hermes Pro is an operational system for digital-product production and optimization. Its core loop is:

`Radar → Product → Offer → Publish → Sell → Analytics → Next experiment`

The product should make the user's next profitable experiment obvious without claiming that any result is guaranteed.

## Existing Constraints

- Keep the existing frontend/backend split.
- Keep Vercel for the frontend.
- Keep Render for API and worker deployment.
- Keep Supabase for database/storage/auth where already used.
- Keep Gemini as the AI provider already configured in the project.
- Keep Hotmart as the current sales-platform integration.
- Keep Telegram for notifications.
- Keep Redis for queued/worker work where already configured.
- Do not add Eduzz, Kiwify, or unrelated marketplaces to this scope.
- Never place API keys or secrets in source code.
- Preserve `/` and `/health` API endpoints.
- The interface must work well on mobile first and remain usable on desktop.

## Information Architecture

### Primary navigation

1. **Início** — command center and system health.
2. **Produtos** — product catalog, statuses, revenue and actions.
3. **Fábrica** — guided product-generation workflow.
4. **Radar** — opportunity discovery and scoring.
5. **Vendas** — sales/revenue metrics from connected sales data.
6. **Analytics** — product performance and recommended experiments.
7. **Agentes** — agent status, jobs, logs and capabilities.

On small screens this becomes a compact bottom navigation with a prominent create action.

## Command Center

The home screen must prioritize business state rather than technical implementation details.

Required cards/sections:

- Revenue summary when sales data exists.
- Product count and active jobs.
- Current product-generation pipeline.
- System integration health: API, worker, database, AI, Hotmart, Telegram.
- Recent sales/events when available.
- A primary `Criar produto` action.
- Actionable insight when analytics data exists.

If data is unavailable, show an explicit empty state instead of fabricated metrics.

## Product Studio

A product creation flow accepts a topic and produces structured stages:

1. Idea/topic.
2. Opportunity analysis.
3. Audience and positioning.
4. Title/subtitle.
5. Outline.
6. Content generation.
7. Quality review.
8. Cover asset.
9. PDF/document package.
10. Offer metadata.
11. Publication preparation.

Each stage must expose status (`queued`, `running`, `completed`, `failed`) and a useful error message when applicable.

## Radar

The Radar presents opportunities using a transparent score rather than unexplained AI confidence.

Score dimensions:

- demand signal;
- competition;
- differentiation potential;
- production difficulty;
- pricing potential;
- target-audience clarity.

The first implementation may use deterministic weighted scoring over available research signals. Missing signals must lower confidence rather than invent values.

## Quality Control

Before publication, the product should receive a QA report covering:

- structure;
- readability;
- coherence;
- originality-risk signals;
- formatting;
- offer clarity.

QA must return a score plus concrete findings. Automatic correction must be available only when the underlying content is editable and the operation is safe/idempotent.

## Sales and Analytics

Sales data must be represented with:

- revenue;
- order count;
- average ticket when enough data exists;
- product-level performance;
- time ranges.

Analytics converts observed performance into explicit suggestions such as testing a related product, changing positioning, or reviewing an underperforming offer. Suggestions are recommendations, not guarantees.

## Agent System

Replace placeholder/pass-through business behavior only where the current scope needs it. Agent contracts should remain small and independently testable.

Initial logical agents:

- `radar` — opportunity analysis;
- `strategist` — product positioning;
- `writer` — product content;
- `editor` — QA and revision;
- `designer` — cover/visual preparation;
- `publisher` — publication payload preparation;
- `analyst` — performance analysis;
- `guardian` — safety/reliability checks;
- `watchtower` — system monitoring.

Agent execution must be represented as jobs with IDs, status, timestamps and error details. Long-running generation must not block the HTTP request.

## Reliability

The product must fail visibly and recoverably.

Required patterns:

- API timeouts around external calls.
- Retry only for transient failures and with bounded attempts.
- Idempotency for publication/event handlers where duplicate delivery is possible.
- Structured error responses.
- Frontend loading, empty and error states.
- Health/readiness checks.
- Worker/job status visibility.
- No fabricated success, sales, or integration state.

## Visual System

Direction: dark luxury / high-contrast operational dashboard.

- Near-black base.
- Warm metallic/gold accent used sparingly for primary actions and key numbers.
- Muted neutral surfaces.
- Strong typographic hierarchy.
- Rounded but restrained cards.
- Subtle gradients and motion only where they communicate state.
- Avoid dashboard clutter and decorative widgets without business value.

The interface should feel like a premium control room, not a generic SaaS admin template.

## Responsive Behavior

Mobile is the primary layout target:

- one-column content flow;
- thumb-friendly controls;
- sticky primary action where appropriate;
- bottom navigation;
- readable tables transformed into cards where necessary;
- no horizontal scrolling for core workflows.

Desktop may expand the same information into a sidebar and multi-column dashboard without creating a separate product architecture.

## Data and API Boundaries

The frontend should consume explicit API resources instead of embedding business rules in presentation components.

Target resource groups:

- `/health` and system status;
- `/api/v1/agents`;
- product/job resources;
- radar/opportunity resources;
- sales/analytics resources;
- integration status resources.

Only implement resource groups that can be backed by real persistence or clearly labeled demo/empty states. Do not hard-code fake production metrics.

## Testing Requirements

Frontend:

- production build must pass;
- critical workflow rendering must be testable;
- API failures must render an error state;
- empty datasets must render empty states;
- mobile layout must avoid overflow in the main workflow.

Backend:

- root and health endpoints;
- agent registry/listing;
- agent execution contract;
- validation failures;
- transient external failure handling where implemented;
- job state transitions for asynchronous work.

Integration/deployment:

- CI must run tests and frontend build;
- Vercel must build the `frontend` application from the repository root configuration;
- Render API must expose `/` and `/health`.

## Delivery Order

### Phase 1 — Reliable shell

Build the premium responsive shell, navigation, command center, system status, product catalog and robust loading/error/empty states.

### Phase 2 — Product engine

Implement product jobs, Radar, Product Studio, QA and document/cover pipeline using the existing backend abstractions and configured AI service.

### Phase 3 — Commercial loop

Connect Hotmart sales events/data, Telegram notifications, sales dashboard, analytics and recommendation loop.

### Phase 4 — Hardening

Add observability, retry/idempotency rules, CI smoke tests and deployment verification.

## Success Criteria

A user can open Hermes Pro on a phone, understand the state of the business in seconds, start a product from a topic, see its progress, review its output, prepare it for Hotmart, receive relevant Telegram events, and inspect real sales/performance data when integrations are configured. If an integration is unavailable, Hermes clearly reports the state instead of pretending it is connected.
