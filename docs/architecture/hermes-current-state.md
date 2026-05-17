# Hermes Current State

> **Document Status**: Baseline audit as of 2026-05-16  
> **Owner**: Orchestrator (Hermes Adapter Working Group)  
> **Related**: `docs/relic-hermes-upgrade-pack/README.md`, `docs/01-upgrade-proposal.md`

---

## Executive Summary

This document captures the **actual state** of the Relic–Hermes integration boundary as of 2026-05-16. The upgrade plan (`docs/relic-hermes-upgrade-pack`) proposed a `relic.hermes_adapter` package; implementation evolved into a **distributed adapter surface** across multiple modules.

**Key finding**: Most boundary concepts survived; module names, file paths, and trace architecture diverged during implementation.

---

## Design Principle

> **Hermes is runtime. Relic is governance.**

| Layer | Responsibilities |
|-------|-----------------|
| **Hermes** | Sessions, gateways, tool execution, plugin lifecycle, approvals, cron/watchers, delivery surfaces, external observability |
| **Relic** | Subject identity, evidence admission, context pack construction, policy snapshots, correction state, trace artifacts, output criticism, proactive decision logic, audit rules |

---

## Module Inventory

### Implemented Modules

| Module | Location | Lines | Purpose |
|--------|----------|-------|---------|
| `hermes_runtime` | `relic/hermes_runtime.py` | 715 | Session keys, delivery gate, `RuntimeDecision` enum, render configs |
| `hermes_plugin` | `relic/hermes_plugin/` | ~800 | Context injection, fail-safe, plugin lifecycle, tool permissions, memory provider |
| `gumi_plugin.cron_wiring` | `relic/gumi_plugin/cron_wiring.py` | ~200 | No-agent cron decisions, quiet hours, delivery windows |
| `checkin` | `relic/checkin/` | ~400 | Check-in scheduler, question engine, facet updater, anti-repeat logic |
| `chronicle` | `relic/chronicle/` | ~1500 | Trace ledger: dual-write SQLite + JSONL, redaction, consent gate, retention |
| `gumi_continuity` | `relic/gumi_continuity/` | ~600 | Continuity service, admission policy, shared state |

### Missing Modules (Adapter Façade)

| Module | Proposed Location | Status | Notes |
|--------|-------------------|--------|-------|
| `hermes_adapter` | `relic/hermes_adapter/` | **Not created** | Formal adapter façade missing |
| `envelope.py` | `relic/hermes_adapter/envelope.py` | **Gap** | `HermesRuntimeEnvelope` dataclass not defined |
| `identity.py` | `relic/hermes_adapter/identity.py` | **Gap** | `sender_id` → `subject_ref` mapping policy |
| `hooks.py` | `relic/hermes_adapter/hooks.py` | **Gap** | Adapter wrapper for Hermes entrypoint |
| `handoff_gate.py` | `relic/hermes_adapter/handoff_gate.py` | **Gap** | `/handoff` authorization logic |
| `cron_bridge.py` | `relic/hermes_adapter/cron_bridge.py` | **Gap** | `RuntimeDecisionResult` dataclass + wrapper |
| `observability.py` | `relic/hermes_adapter/observability.py` | **Gap** | Langfuse bridge with redaction |
| `approvals.py` | `relic/hermes_adapter/approvals.py` | **Gap** | Approval event normalization |
| `prompt_cache.py` | `relic/hermes_adapter/prompt_cache.py` | **Gap** | Cache invalidation policy |
| `source_policy.py` | `relic/hermes_adapter/source_policy.py` | **Gap** | Source-class taxonomy enforcement |

---

## Entrypoint Analysis

### Current: `hermes-plugin/tools/relic_shared_continuity/hooks.py`

**Location**: `hermes-plugin/tools/relic_shared_continuity/hooks.py` (212 LoC)

**Hooks implemented**:

| Hook | Status | Behavior |
|------|--------|----------|
| `pre_llm_call` | Live | Builds `PromptContextPack` via `ContinuityAdmissionPolicy`, returns `None` or `{"context": str}`, fail-closed on exceptions |
| `transform_llm_output` | Live | Runs `OutputCritic`, falls back to clinical-term filter, returns `None`, `"[SILENT]"`, or replacement string |
| `post_llm_call` | Live | No-op |

**Direct imports** (no adapter indirection):

```python
from relic.gumi_continuity.admission import ContinuityAdmissionPolicy
from relic.context_pack.builder import PromptContextPackBuilder
from relic.shared_continuity.service import ContinuityService
from relic.patterns.signal_extractor import extract_continuity_signals
from relic.safety.escalation_notifier import notify_escalation
from relic.gumi_plugin.critic import OutputCritic
```

**Required upgrades**:

1. Emit Chronicle events on context pack request, admitted items, blocked items, output review, output block
2. Read `chat_id` from `hook_ctx`
3. Consume `HermesRuntimeEnvelope` instead of raw kwargs
4. Preserve every existing acceptance test in `tests/hermes_compat/`

---

## Chronicle Trace Ledger

### Architecture

Chronicle replaced the planned thin `relic/trace/` JSONL sink with a **dual-write** architecture:

- Event Emitter (`relic/chronicle/emitter.py`)
- Dual write to SQLite DB (structured) + JSONL Files (append-only)

### Schema Migrations

| Migration | Purpose |
|-----------|---------|
| `0003_chronicle_events.sql` | Core event table (type, timestamp, subject_id, session_id, redacted payload) |
| `0004_chronicle_decisions.sql` | Decision records (admission, delivery, handoff, approval) |
| `0005_chronicle_state_snapshots.sql` | Periodic state snapshots for audit |
| `0006_chronicle_provenance_edges.sql` | Provenance tracking (event → decision → outcome) |
| `0007_chronicle_access_log.sql` | Access audit (who read what, when) |

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| `Event` | `relic/chronicle/schema.py` | Pydantic model for event structure |
| `emit()` | `relic/chronicle/emitter.py` | Dual-write emitter |
| `read()` | `relic/chronicle/reader.py` | Query interface |
| `redact()` | `relic/chronicle/redaction.py` | PII/sensitive data removal |
| `ConsentGate` | `relic/chronicle/consent_gate.py` | Consent-based admission |
| `RetentionReaper` | `relic/chronicle/retention.py` | GDPR-style deletion |
| `AccessAudit` | `relic/chronicle/access_audit.py` | Access logging |

### Event Types (Partial Catalogue)

Defined in `relic/chronicle/schema.py` and `relic/chronicle/enums.py`:

- `CONTEXT_PACK_REQUESTED`
- `CONTEXT_ITEM_ADMITTED`
- `CONTEXT_ITEM_BLOCKED`
- `OUTPUT_REVIEWED`
- `OUTPUT_BLOCKED`
- `DELIVERY_DECISION`
- `HANDOFF_AUTHORIZED`
- `HANDOFF_BLOCKED`
- `APPROVAL_REQUESTED`
- `APPROVAL_GRANTED`
- `APPROVAL_DENIED`
- `PROACTIVE_CHECKIN_SCHEDULED`
- `PROACTIVE_MESSAGE_DELIVERED`
- `PROACTIVE_MESSAGE_BLOCKED`

---

## Test Coverage

### Test Directories

| Directory | Files | Purpose |
|-----------|-------|---------|
| `tests/chronicle/` | 12 | Chronicle emitter, reader, redaction, consent, retention |
| `tests/hermes/` | 10 | Hermes contract tests (session key, delivery gate, rollback, resume) |
| `tests/hermes_compat/` | 8 | Compatibility tests (plugin injection, context pack, soul isolation) |
| `tests/hermes_plugin/` | 10 | Plugin lifecycle, tool permissions, memory provider |

### Test Results (2026-05-16)

```
tests/hermes_compat/  → 93 passed
tests/hermes/         → 91 passed
tests/chronicle/      → 196 tests
```

---

## Schemas

### Live Schemas (`schemas/hermes/`)

| Schema | Purpose |
|--------|---------|
| `checkpoint.schema.json` | Checkpoint state serialization |
| `delivery_gate.schema.json` | Delivery gate decision format |
| `no_agent_cron_mode.schema.json` | Cron mode flags |
| `platform_allowlist.schema.json` | Platform allowlist structure |
| `rollback_flag.schema.json` | Feature rollback flags |
| `session_key.schema.json` | Session key derivation metadata |
| `transform_llm_output_hook.schema.json` | Transform hook I/O |

### Forward-Target Schemas (Upgrade Pack Only)

| Schema | Location | Status |
|--------|----------|--------|
| `hermes_runtime_envelope.schema.json` | `docs/relic-hermes-upgrade-pack/schemas/` | Not implemented |
| `relic_trace_event.schema.json` | `docs/relic-hermes-upgrade-pack/schemas/` | Superseded by `relic/chronicle/schema.py::Event` |

---

## Gap Analysis

### Phase 1: Runtime Envelope — OPEN

**Missing**:
- `HermesRuntimeEnvelope` dataclass
- Identity mapping policy (`sender_id` → `subject_ref`)
- Schema validation tests

**Impact**: Hooks consume raw kwargs; no normalized boundary object.

---

### Phase 2: Chronicle Alignment — PARTIAL

**Done**:
- Chronicle implementation (dual-write, redaction, consent, retention)
- Migrations 0003–0007
- Test coverage

**Missing**:
- Event-type catalogue file (single source of truth)
- JSON Schema regeneration from `Event` model (or retirement of JSON Schema)
- Adapter-side helper for canonical event emission

**Impact**: Event types defined in code, not documented centrally.

---

### Phase 3: Hook Migration — OPEN

**Done**:
- Hooks functional in `hermes-plugin/tools/relic_shared_continuity/hooks.py`
- Acceptance tests passing

**Missing**:
- Adapter wrapper (`relic/hermes_adapter/hooks.py`)
- Chronicle event emission from hooks
- `chat_id` handling
- Envelope consumption

**Impact**: Direct coupling between Hermes entrypoint and Relic internals.

---

### Phase 4: Cron Bridge — PARTIAL

**Done**:
- `relic/gumi_plugin/cron_wiring.py` — no-agent cron logic
- `relic/checkin/scheduler.py` — check-in scheduling
- `RuntimeDecision` enum in `relic/hermes_runtime.py`

**Missing**:
- `RuntimeDecisionResult` dataclass (with `reason_codes`, `subject_ref`, `candidate_message`, `media_type`, `trace_event_id`)
- Bridge function wrapping cron logic
- Contract tests in `tests/hermes/test_cron_bridge_contract.py`

**Impact**: Cron decision logic not exposed via stable interface.

---

### Phase 5: Handoff Gate — OPEN

**Missing**:
- `relic/hermes_adapter/handoff_gate.py`
- `HandoffDecision` dataclass
- Authorization tests

**Impact**: `/handoff` feature not governed by Relic policy.

---

### Phase 6: Approvals + Observability — OPEN

**Missing**:
- `relic/hermes_adapter/approvals.py` — approval event normalization
- `relic/hermes_adapter/observability.py` — Langfuse bridge with redaction
- `relic/hermes_adapter/prompt_cache.py` — cache invalidation policy
- Redaction tests for external observability
- Cache policy tests

**Impact**: No governed approval flow; no redacted observability bridge.

---

### Phase 7: Source Policy Unification — OPEN

**Done**:
- Admission logic in `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py`

**Missing**:
- `relic/hermes_adapter/source_policy.py` — single taxonomy
- `classify(envelope) -> SourceClass` function
- `is_evidence_eligible(source_class, consent_state) -> bool` function
- Migration of callers to unified taxonomy

**Impact**: Source-class taxonomy not enforced uniformly.

---

### Phase 8: Documentation — PARTIAL

**Done**:
- `docs/relic-hermes-upgrade-pack/README.md`
- `docs/relic-hermes-upgrade-pack/docs/01-upgrade-proposal.md`
- `docs/relic-hermes-upgrade-pack/docs/02-agentic-development-plan.md`
- `docs/guides/hermes-integration.md` (existing)

**Missing**:
- `docs/architecture/hermes-current-state.md` (this document)
- `docs/architecture/trace-ledger.md` (Chronicle)
- `docs/guides/hermes-v2026-5-16-upgrade.md`
- `docs/reference/hermes-adapter.md`
- `CHANGELOG.md` entry

---

## Recommended Next Steps

### Immediate (Phase 1)

1. Create `relic/hermes_adapter/` package
2. Implement `envelope.py` with `HermesRuntimeEnvelope`
3. Implement `identity.py` with mapping policy
4. Write tests in `tests/hermes_compat/test_runtime_envelope.py`

### Parallel (Phase 2)

1. Generate event-type catalogue from `relic/chronicle/schema.py`
2. Decide: regenerate JSON Schema or retire in favor of Pydantic source-of-truth
3. Document canonical event types in `docs/architecture/trace-ledger.md`

### Sequential (Phases 3–7)

Follow the worker roster in `docs/relic-hermes-upgrade-pack/docs/02-agentic-development-plan.md`.

---

## Branch Strategy

Use small branches for independent review:

```
upgrade/hermes-envelope
upgrade/chronicle-event-types-catalogue
upgrade/hermes-hook-adapter
upgrade/hermes-cron-bridge
upgrade/hermes-handoff-gate
upgrade/hermes-approvals
upgrade/hermes-observability-cache
upgrade/hermes-source-policy
upgrade/hermes-docs
```

---

## Review Gates

A task is not merge-ready unless:

- Tests pass (run sequentially, no parallelism)
- New behaviour has contract tests
- Redaction behaviour is tested
- Docs updated when public behaviour changes
- No raw user data in public traces or external observability
- No second scheduler or delivery authority introduced
- No Gumi diegetic events treated as subject evidence
- No existing `OutputCritic` behaviour weakened
- Existing `hermes-plugin` loading contract preserved

---

## References

- `docs/relic-hermes-upgrade-pack/README.md` — Upgrade pack overview
- `docs/relic-hermes-upgrade-pack/docs/01-upgrade-proposal.md` — Detailed proposal
- `docs/relic-hermes-upgrade-pack/docs/02-agentic-development-plan.md` — Worker plan
- `relic/hermes_runtime.py` — Runtime decision logic
- `relic/chronicle/schema.py` — Event schema
- `hermes-plugin/tools/relic_shared_continuity/hooks.py` — Hermes entrypoint
