# Hermes Autonomous Commerce Engine

## Objective

Hermes is a private, continuously running commerce engine. It is not limited to ebook generation. It discovers legal product and service opportunities, validates them with available evidence, scores economics and execution risk, produces or executes approved work, performs QA, publishes only through authorized channel capabilities, measures results, and feeds verified outcomes back into the next cycle.

## Economic rule

The optimization metric is:

`revenue - AI cost - infrastructure cost - advertising cost - other recorded costs = estimated operating profit`

R$900/day is an optimization target, not a guaranteed result. Missing signals reduce confidence instead of being fabricated.

## Opportunity engine

Each opportunity is one of `product` or `service` and carries source, source URL when known, signals, score, confidence, status, metadata, and idempotency key.

Score dimensions:

- demand
- margin
- ease
- conversion probability
- execution capacity
- competition
- cost
- risk

Positive dimensions increase the score; competition, cost, and risk reduce it. Confidence is the fraction of required signals actually supplied.

## Product engine

Supported legal digital products include ebooks, guides, checklists, templates, spreadsheets, kits, educational materials, packs, and other permitted digital products. The existing ebook pipeline remains a product execution capability.

Product execution must remain persistent and idempotent. Required QA covers content coherence, unsupported claims, contradictions, files, offer metadata, originality/licensing risk, and publication readiness. A failed QA result blocks publication.

## Service engine

Service opportunities cover permitted freelance work such as writing, design, translation, research, automation, programming, data analysis, and document production. Hermes stores briefing, difficulty, estimated hours, value, cost, profit, status, and metadata. It does not bypass marketplace rules or use prohibited scraping/automation.

## Controls

Persistent controls include global kill switch, paused domains, AI/ads/total budgets, and human approval mode. Every spend, publish, and execution action must pass the control gate. A blocked operation must return an explicit reason.

## Jobs and agents

Jobs use persistent state and idempotency. The target state machine is:

`PENDING -> RUNNING -> QA -> APPROVED -> PUBLISHED -> MONITORING -> COMPLETED`

with `FAILED`, `RETRYING`, `BLOCKED`, and `CANCELLED` as terminal or recovery states.

Agents have bounded capabilities and return explicit run state. Guardian is the final policy/control gate before publication or spending.

## Channels

Channel adapters expose product creation, file upload, pricing, publication, product lookup, sales/orders, status, and webhook handling. Hotmart is the first commercial channel and must use official APIs and configured credentials. If a capability is unavailable, Hermes reports unavailable instead of pretending it succeeded.

## Notifications

Telegram is an optional notification adapter. Missing credentials produce `not_configured`; failed API calls produce an error state; only confirmed API success is reported as sent.

## Data and security

Supabase stores opportunities, scores, services, expenses, settings, events, agent runs, products, jobs, and sales events. New private system tables have RLS enabled. The backend may use its server-side secret key; no service-role/secret key is ever exposed to the browser.

## Command center

The web panel is the single operating surface for status, products, factory jobs, radar/opportunities, services, sales, analytics, agents, logs, health, and controls. Real values are read from the API. Unknown values are shown as unavailable rather than invented.

## 24/7 operation

The API, persistent queue, worker, scheduler/recovery loop, Supabase state, AI gateway, channel adapters, and notification adapters form the operating loop:

`discover -> validate -> score -> decide -> produce/execute -> QA -> publish/deliver -> measure -> optimize -> repeat`

Recovery uses persisted job state, retries with bounded attempts, and idempotency keys so restarts do not duplicate products or external operations.
