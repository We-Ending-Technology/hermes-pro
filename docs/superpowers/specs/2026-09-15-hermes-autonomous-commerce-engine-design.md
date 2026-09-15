# Hermes Autonomous Commerce Engine — Definitive Design

## Objective

Hermes is a private, continuously operating revenue-opportunity system. It discovers economically interesting opportunities, validates evidence, chooses between digital products and legitimate services, executes bounded work, performs QA, prepares/publishes through supported channels, measures real revenue and costs, and optimizes the next cycle.

The system must never treat an estimate as a sale, a draft as a publication, or a target as a result.

## Economic Objective

Primary operating metric:

`estimated operating profit = realized revenue - AI cost - infrastructure cost - advertising cost - other recorded costs`

R$900/day is an optimization target only. It is not a guarantee or an assumed baseline.

## Opportunity Engine

Each opportunity has:
- source and observed timestamp
- type: product or service
- evidence payload
- demand signal
- competition signal
- differentiation
- production/execution difficulty
- pricing potential
- audience clarity
- estimated revenue
- estimated direct cost
- estimated margin
- risk
- confidence
- score
- recommended action
- lifecycle status
- idempotency key

Score is deterministic from normalized evidence. Missing evidence lowers confidence and cannot be replaced by invented numbers.

## Products

Supported legal digital-product classes include ebook, guide, checklist, template, spreadsheet, kit, educational material, pack, and other non-restricted digital goods.

Product lifecycle:
`DISCOVERED -> BRIEFED -> PRODUCING -> QA -> APPROVED -> READY_TO_SELL -> PUBLISHED -> MONITORING -> COMPLETED`

Failure states:
`FAILED`, `RETRYING`, `BLOCKED`, `CANCELLED`.

Existing PDF/DOCX/cover generation remains reusable. QA must block publication when required checks fail.

## Services

Service opportunities are discovered and classified by briefing clarity, capability compatibility, difficulty, time, value, margin, risk, and permitted platform mechanism.

Hermes may prepare a proposal/brief automatically. External submission or execution occurs only through an officially supported mechanism and only when platform terms permit it. No scraping, credential abuse, or hidden automation is allowed.

## Agents

Named bounded agents:
- Radar
- Market Intelligence
- Product
- Service
- Design
- Document
- QA/Editor
- Marketplace/Publisher
- Sales
- Analytics
- Optimizer
- Guardian
- Watchtower

An optional Core/CEO orchestrator coordinates them. Each run has an ID, timestamps, status, input/output metadata, cost estimate/actual where available, permissions, and errors.

Agents do not receive unrestricted external side effects. Side effects are mediated by services and channel adapters.

## Job System

Every durable operation has a job ID and idempotency key.

Primary states:
`PENDING -> RUNNING -> QA -> APPROVED -> PUBLISHED -> MONITORING -> COMPLETED`

Alternative states:
`FAILED`, `RETRYING`, `BLOCKED`, `CANCELLED`.

Retries use bounded exponential backoff. Stale jobs are recoverable. Repeated execution must not create duplicate products or duplicate external actions.

## QA

QA covers:
- content coherence and contradictions
- unsupported or suspicious claims
- file validity and size
- offer completeness
- title/description/price/assets
- originality/license/copyright risk
- channel readiness

Only safe, idempotent corrections may be automatic. A failed QA result identifies the owner, corrects where safe, and runs QA again. Publication is impossible while QA is failed.

## Channels

Channel adapters expose:
`create_product`, `upload_file`, `set_price`, `publish`, `get_product`, `get_sales`, `get_orders`, `get_status`, `receive_webhook`.

Hotmart is the first marketplace adapter. A product is considered published or sold only after confirmed platform evidence. Telegram is an alert channel and only reports successful delivery after the provider confirms it.

Other connected tools may contribute research, analytics, design, CRM, project management, or automation capability, but only through supported actions and without inventing API capabilities.

## Costs and Analytics

Record AI, infrastructure, advertising, marketplace, and other operational expenses when evidence is available. Analytics separates realized values from estimates. Profit is never inferred from a target, listing price, or expected conversion.

## Controls

Controls include:
- global kill switch
- factory stop
- radar stop
- publishing stop
- agent stop
- product stop
- spend stop
- advertising stop
- daily AI budget
- daily advertising budget
- total daily budget
- approval mode

Budget and kill-switch checks execute before expensive or external side effects.

## Memory and Events

Persistent memory records opportunities, decisions, jobs, agent runs, product versions, costs, events, experiments, sales/orders, health, settings, and audit events.

All state-changing operations create auditable events with actor/source, timestamp, entity, action, and result.

## 24/7 Runtime

Deployment model:
- Vercel frontend
- Render API
- Render worker or embedded worker where configured
- persistent Supabase database/storage
- scheduler/cron
- AI through backend gateway/API
- optional Telegram notifications

Runtime requirements:
- retries and backoff
- idempotency
- stale-job recovery
- health monitoring
- provider fallback when configured
- budget enforcement
- no fabricated state

## Command Center

The single web panel exposes:
- Início
- Produtos
- Fábrica
- Radar
- Serviços
- Vendas
- Analytics
- Agentes
- Logs/Eventos
- Saúde
- Controles

The interface must show real state and clearly distinguish unavailable/unconfigured integrations.

## Chat Commands

Examples:
- `Encontre oportunidades para hoje.`
- `Encontre algo que possa gerar pelo menos R$300.`
- `Produza os três melhores produtos.`
- `Procure trabalhos freelance compatíveis.`
- `Pause tudo que estiver dando prejuízo.`
- `Explique por que as vendas caíram.`

Commands that cause side effects must be routed through the same permission, budget, idempotency, and audit controls as UI actions.

## Security and Truthfulness

Secrets remain in environment/secret stores. Never commit credentials. Never claim connector access that has not been verified. Never report a sale, publication, delivery, or profit without persisted evidence.

## Connector Strategy

Use connected capabilities when they materially help: GitHub, Vercel, Render, Supabase, Sentry, PostHog, Canva, Mapify, Firecrawl, BrowserAct, AdKit, HubSpot, Ahrefs, Similarweb, Notion, Asana, Airtable, Linear, Slack, and Make where available and permitted.

Unavailable or unsupported integrations remain explicitly marked as such. Gemini remains a backend API integration rather than a separate connector dependency.
