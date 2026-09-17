# Hermes Autonomous Memory & Watchdog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent learning, reflection, event/watchdog automation, CEO delegation, and enforceable autonomy rules to Hermes.

**Architecture:** Supabase stores durable memory, incidents, watchdog state, reflection runs, and policies. A deterministic watchdog and autonomy policy layer controls actions; the CEO/orchestrator delegates specialist work and the reflection engine consolidates verified outcomes. Existing product/radar/worker systems remain the execution layer.

**Tech Stack:** FastAPI, Python async services, Supabase REST/Postgres migrations, existing agent registry, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-hermes-autonomous-memory-watchdog-design.md`

## Global Constraints

- Keep Supabase RLS enabled; never expose service/secret keys to the frontend.
- No autonomous action may bypass kill-switch, budget, idempotency, or approval policy.
- Never promote an unverified claim to durable memory.
- Never claim an incident is resolved without a verification result.
- Every new behavior gets a failing test before implementation.
- Preserve existing API contracts and product-generation behavior.

---

### Task 1: Persistent autonomy schema

**Files:**
- Create: `supabase/migrations/20260917_autonomy_memory_watchdog.sql`
- Test: `backend/tests/test_autonomy_schema_contract.py`

- [ ] Write failing tests asserting required tables/columns are represented by the migration contract.
- [ ] Verify the tests fail for the current migration set.
- [ ] Add tables for memories, incidents, watchdog checks, reflection runs, and autonomy policies with indexes and RLS enabled.
- [ ] Add uniqueness for incident fingerprints and memory identifiers where appropriate.
- [ ] Run schema contract tests.
- [ ] Commit.

### Task 2: Memory engine

**Files:**
- Create: `backend/app/services/memory.py`
- Test: `backend/tests/test_memory.py`

- [ ] Write failing tests for candidate lesson creation, evidence-backed promotion, retrieval, stale marking, and rejection.
- [ ] Verify red.
- [ ] Implement the smallest persistence abstraction using the existing `SupabaseREST` interface.
- [ ] Ensure retrieval filters out rejected lessons and orders active lessons by confidence/relevance.
- [ ] Run memory tests.
- [ ] Commit.

### Task 3: Autonomy policy engine

**Files:**
- Modify: `backend/app/services/controls.py`
- Test: `backend/tests/test_autonomy_policy.py`

- [ ] Write failing tests for observe/reversible/financially-bounded/human-approval actions.
- [ ] Verify red.
- [ ] Implement explicit policy evaluation with kill switch and budget checks.
- [ ] Preserve current control API compatibility.
- [ ] Run policy tests.
- [ ] Commit.

### Task 4: Incident and watchdog engine

**Files:**
- Create: `backend/app/services/watchdog.py`
- Test: `backend/tests/test_watchdog.py`

- [ ] Write failing tests for stalled-job detection, provider-error detection, incident fingerprint deduplication, bounded retry, and escalation.
- [ ] Verify red.
- [ ] Implement cheap deterministic checks over existing jobs/system state.
- [ ] Persist watchdog check state and incidents.
- [ ] Ensure repeated failures update one incident rather than creating a storm.
- [ ] Run watchdog tests.
- [ ] Commit.

### Task 5: CEO hierarchy and reflection engine

**Files:**
- Create: `backend/app/services/reflection.py`
- Modify: `backend/app/services/orchestrator.py`
- Test: `backend/tests/test_reflection.py`
- Test: `backend/tests/test_orchestrator_autonomy.py`

- [ ] Write failing tests for CEO delegation, memory lookup before action, reflection promotion, and no-action escalation.
- [ ] Verify red.
- [ ] Implement deterministic orchestration around specialist agents.
- [ ] Implement reflection as a bounded, non-blocking consolidation pass.
- [ ] Record outcomes as memory candidates only when evidence supports them.
- [ ] Run tests.
- [ ] Commit.

### Task 6: Autonomous lifecycle integration

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_autonomous_lifecycle.py`

- [ ] Write failing tests for watchdog/reflection invocation from the autonomous heartbeat.
- [ ] Verify red.
- [ ] Add watchdog execution before autonomous production decisions and reflection after enough evidence exists.
- [ ] Ensure exceptions become incidents rather than disappearing in broad catches.
- [ ] Keep the heartbeat bounded so watchdog/reflection cannot starve product work.
- [ ] Run lifecycle tests.
- [ ] Commit.

### Task 7: Operational API visibility

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_autonomy_api.py`

- [ ] Write failing tests for memory, incidents, watchdog status, reflection status, and autonomy policy endpoints.
- [ ] Verify red.
- [ ] Add read-only operational endpoints and guarded control endpoints where needed.
- [ ] Return truthful status only; never expose secrets.
- [ ] Run API tests.
- [ ] Commit.

### Task 8: End-to-end verification

**Files:**
- Modify: tests/docs only if failures require it.

- [ ] Run the complete backend suite.
- [ ] Run frontend tests/build.
- [ ] Run migration/schema checks available in CI.
- [ ] Verify a repeated incident deduplicates.
- [ ] Verify a blocked action stays blocked under kill switch/budget.
- [ ] Verify memory survives process restart by using persistence rather than in-memory state.
- [ ] Verify the autonomous loop records failures rather than silently swallowing them.
- [ ] Only then mark the implementation complete.
