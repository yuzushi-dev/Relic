# Agentic Development Plan

> **Revision 2026-05-16** — re-phased against actual codebase state. Phases marked `DONE` and `PARTIAL` describe what already shipped; phases `OPEN` describe remaining work. Worker rosters and gates unchanged in principle.

## Operating model

One orchestrator and several bounded implementation workers. Orchestrator owns architecture, task sequencing, review, merge readiness, contract enforcement. Workers receive narrow packets with explicit files, output expectations, tests, stop conditions.

Boundary rule, repeated every packet:

**Hermes is runtime. Relic is governance.**

## Roles

Roster preserved from the original plan. Ownership is now scoped to gaps in the current tree.

### Orchestrator

- keep implementation aligned with `docs/01-upgrade-proposal.md`
- split work into small branches or task packets
- prevent scope creep
- reject changes that move Relic governance into Hermes runtime assumptions
- enforce tests and docs updates
- require redaction tests for trace and observability work
- keep compatibility with the existing Hermes plugin entrypoint (`hermes-plugin/tools/relic_shared_continuity/hooks.py`)
- decide adapter path: **rebrand** (alias adapter names onto existing modules) vs **façade** (new `relic/hermes_adapter/` wrapping existing code). All packets below assume **façade**.

### Worker A: Hermes adapter (envelope + identity)

Owns:

- `relic/hermes_adapter/__init__.py`
- `relic/hermes_adapter/envelope.py`
- `relic/hermes_adapter/identity.py`
- adapter dataclasses or pydantic models
- schema validation tests in `tests/hermes_compat/test_runtime_envelope.py`

### Worker B: Trace ledger (Chronicle alignment)

Chronicle already exists. Worker B no longer writes a new trace ledger. Owns:

- generation of `schemas/relic_trace_event.schema.json` from `relic/chronicle/schema.py::Event` (or retirement of the JSON Schema in favour of the Pydantic source-of-truth)
- canonical event-type catalogue file (e.g. `relic/chronicle/event_types.py` or docstring constants)
- adapter-side helper that emits Chronicle events with the canonical types
- regression tests asserting adapter emits the catalogue types

### Worker C: Hook migration

Owns:

- `relic/hermes_adapter/hooks.py`
- thin shim in `hermes-plugin/tools/relic_shared_continuity/hooks.py` delegating to the adapter
- pre-LLM context injection tests (extending `tests/hermes_compat/test_plugin_context_injection.py`)
- output critic pass-through and block tests
- new `tests/hermes_compat/test_hook_trace_events.py`

### Worker D: Cron and watcher bridge

Owns:

- `relic/hermes_adapter/cron_bridge.py`
- `RuntimeDecisionResult` dataclass (consider re-using fields from `relic/hermes_runtime.py::RuntimeDecision` enum)
- wrapper around `relic/gumi_plugin/cron_wiring.py` and `relic/checkin/scheduler.py`
- contract tests in `tests/hermes/test_cron_bridge_contract.py` (sits next to existing `test_no_agent_cron_mode_contract.py`)
- ensure compatibility with current `tests/hermes/test_no_agent_cron_wiring.py`

### Worker E: Handoff and approvals

Owns:

- `relic/hermes_adapter/handoff_gate.py`
- `relic/hermes_adapter/approvals.py`
- handoff authorization tests in `tests/hermes_compat/test_handoff_gate.py`
- approval normalization tests in `tests/hermes_compat/test_approval_events.py`

### Worker F: Observability and cache safety

Owns:

- `relic/hermes_adapter/observability.py`
- `relic/hermes_adapter/prompt_cache.py`
- redaction tests in `tests/hermes_compat/test_observability_redaction.py`
- cache invalidation contract tests in `tests/hermes_compat/test_prompt_cache_policy.py`

### Worker G: Documentation and review

Owns:

- `docs/architecture/trace-ledger.md` (Chronicle)
- updates to `docs/architecture/module-map.md` (existing) describing the adapter surface
- `docs/guides/hermes-v2026-5-16-upgrade.md`
- `docs/reference/hermes-adapter.md`
- `CHANGELOG.md` entry
- review checklist

## Phase plan

### Phase 0: Repository audit and baseline — **DONE (2026-05-16)**

Goal: establish current behaviour before changing code.

State:

- The audit in this revision documents 715 LoC `relic/hermes_runtime.py`, 212 LoC `hermes-plugin/tools/relic_shared_continuity/hooks.py`, `relic/hermes_plugin/` module set, `relic/gumi_plugin/cron_wiring.py`, `relic/checkin/`, Chronicle migrations `0003`–`0007`, and the test layout (`tests/chronicle/*`, `tests/hermes/*`, `tests/hermes_compat/*`, `tests/hermes_plugin/*`).
- Remaining deliverable: `docs/architecture/hermes-current-state.md` capturing this audit in the main docs tree (not just in the upgrade pack). Worker G should produce it.

### Phase 1: Runtime envelope — **OPEN**

Goal: add a stable normalized object for Hermes metadata.

Files (to create):

```text
relic/hermes_adapter/__init__.py
relic/hermes_adapter/envelope.py
relic/hermes_adapter/identity.py
tests/hermes_compat/test_runtime_envelope.py
schemas/hermes/runtime_envelope.schema.json    # move pack schema into the live tree
```

Core behaviour (unchanged from original plan):

- build envelope from hook kwargs, environment variables, and Hermes metadata
- prefer explicit hook metadata over environment variables
- hash platform-scoped identifiers before trace export
- handle missing session and chat IDs without throwing
- expose `trace_id`, `session_id`, `chat_id`, `platform`, `sender_ref`, `model`, `turn_index`
- co-exist with `HermesSessionKey` (`relic/hermes_runtime.py`) — envelope should accept a session-key hash for binding rather than deriving its own

Exit criteria:

- tests cover empty metadata, partial metadata, full metadata
- envelope never includes raw message text by default
- schema validates generated samples
- no existing `tests/hermes_compat/*` test regresses

### Phase 2: Trace ledger MVP — **DONE via Chronicle**

Original goal: create an append-only local Relic trace ledger.

State:

- Implemented as **Chronicle** (`relic/chronicle/`). Dual-write JSONL + SQLite. Five record types (Event, Decision, StateSnapshot, ProvenanceEdge, AccessLogEntry). Migrations `0003`–`0007` applied. Redaction (`redaction.py`), consent gate (`consent_gate.py`), retention reaper (`retention.py`), access audit (`access_audit.py`), provenance edges (`provenance.py`) all present. Reader API in `reader.py`. CLI in `relic/chronicle/cli/`.
- Tests: `tests/chronicle/test_emitter.py`, `test_reader.py`, `test_schema.py`, `test_redaction.py`, `test_retention.py`, `test_provenance.py`, `test_snapshots.py`, `test_consent_gate.py`, `test_context.py`, `test_acceptance.py`, `test_access_audit.py` + `fixtures/`.

Remaining alignment work (small):

- Regenerate `schemas/relic_trace_event.schema.json` from `relic.chronicle.schema.Event`, or retire the JSON Schema and treat the Pydantic model as the contract.
- Add a canonical event-type catalogue (Worker B) so adapter modules emit consistent `event_type` strings.
- Add a `docs/architecture/trace-ledger.md` describing Chronicle for outside readers.

Exit criteria for the alignment work:

- JSON Schema and Pydantic model agree on every field
- `event_type` catalogue is import-stable
- Outsider can read Chronicle docs without grepping code

### Phase 3: Hook migration — **OPEN**

Goal: move existing Hermes hook logic into a testable adapter while keeping the plugin entrypoint stable.

Files:

```text
relic/hermes_adapter/hooks.py
hermes-plugin/tools/relic_shared_continuity/hooks.py   # becomes a thin shim
tests/hermes_compat/test_plugin_context_injection.py   # extend
tests/hermes_compat/test_hook_trace_events.py          # new
```

Core behaviour:

- keep current function names: `pre_llm_call`, `post_llm_call`, `transform_llm_output`
- consume an `HermesRuntimeEnvelope` (from Phase 1) instead of raw kwargs
- route implementation through `relic.hermes_adapter.hooks`
- emit Chronicle events for context request, admitted items, blocked items, output review, output block
- preserve existing blocked-item non-injection behaviour
- preserve the `finally`-block safety scan currently in `pre_llm_call`

Exit criteria:

- existing compatibility tests pass unchanged (or imports adjusted)
- new tests confirm Chronicle events are emitted with canonical `event_type`s
- no blocked reason or blocked item appears in injected context

### Phase 4: Cron and watcher bridge — **PARTIAL → OPEN**

Goal: use Hermes no-agent scheduling without duplicating delivery authority.

Files:

```text
relic/hermes_adapter/cron_bridge.py
relic/gumi_plugin/cron_wiring.py                       # unchanged callees
tests/hermes/test_cron_bridge_contract.py              # new
```

Core behaviour:

- expose `evaluate_no_agent_tick(envelope: HermesRuntimeEnvelope) -> RuntimeDecisionResult`
- reuse existing quiet hours, platform allowlist, paused subject, check-in, delivery window rules
- reuse `relic/checkin/scheduler.py` for due-followup checks
- return the structured decision result
- emit Chronicle event for every decision, including `NO_REPLY` and `BLOCKED`
- co-exist with the existing `RuntimeDecision` enum in `relic/hermes_runtime.py` (use it as the `decision` field type)

Exit criteria:

- decisions are deterministic under fixed time and policy fixtures
- delivery never occurs when platform is not allowlisted
- opt-out produces no delivery
- quiet hours produce `BLOCKED`
- existing `tests/hermes/test_no_agent_cron_wiring.py` and `test_delivery_gate.py` still pass

### Phase 5: Governed handoff — **OPEN**

Goal: use Hermes `/handoff` while preventing governance bypass.

Files:

```text
relic/hermes_adapter/handoff_gate.py
tests/hermes_compat/test_handoff_gate.py
```

Core behaviour:

- evaluate handoff request before Hermes executes it
- support `ALLOW_FULL_CONTEXT`, `ALLOW_REDUCED_CONTEXT`, `REBUILD_CONTEXT`, `BLOCK`
- block handoff after correction if context has not been rebuilt
- block handoff that changes subject mapping
- emit Chronicle event for every request and result

Exit criteria:

- tests cover all four results
- handoff cannot bypass `OutputCritic`
- handoff cannot preserve context across policy snapshot changes unless allowed by the gate

### Phase 6: Approvals, observability, cache safety — **OPEN**

Goal: normalize Hermes approval events and export only redacted observability data.

Files:

```text
relic/hermes_adapter/approvals.py
relic/hermes_adapter/observability.py
relic/hermes_adapter/prompt_cache.py
tests/hermes_compat/test_approval_events.py
tests/hermes_compat/test_observability_redaction.py
tests/hermes_compat/test_prompt_cache_policy.py
```

Core behaviour:

- approval request and resolution events become Chronicle events
- Langfuse / external export receives only redacted summary spans
- prompt cache policy exposes allowed sections and invalidation keys
- any cache key missing profile/policy/correction state is invalid

Exit criteria:

- redaction tests fail if raw subject strings appear in external span payloads
- cache tests fail if subject profile text is marked cacheable
- approval events include policy snapshot references

### Phase 7: Source policy unification — **OPEN (new, surfaced from audit)**

Goal: single source-class taxonomy at the runtime boundary.

Files:

```text
relic/hermes_adapter/source_policy.py
tests/hermes_compat/test_source_policy.py
```

Core behaviour:

- enum of source classes per `docs/03-contracts-and-schemas.md`
- single function `classify(envelope) -> SourceClass`
- single function `is_evidence_eligible(source_class, consent_state) -> bool`
- migrate callers in `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py` to consult the taxonomy

Exit criteria:

- `GUMI_DIEGETIC_EVENT` cannot become evidence by default in any caller
- `PUBLIC_WEB_SOURCE` requires explicit user request and provenance
- admission decisions emit Chronicle events with `source_class` in payload

### Phase 8: Documentation and release readiness — **PARTIAL → OPEN**

Goal: make the upgrade maintainable.

Files:

```text
docs/architecture/hermes-current-state.md
docs/architecture/hermes-integration.md     # update existing
docs/architecture/trace-ledger.md           # new — Chronicle
docs/guides/hermes-v2026-5-16-upgrade.md    # new
docs/reference/hermes-adapter.md            # new
CHANGELOG.md                                 # new entry
```

Exit criteria:

- user can understand the runtime boundary without reading code
- contributor can add a new Hermes platform source without violating source policy
- release notes include migration notes and known limitations

## Branching strategy

Use small branches:

```text
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

Avoid one large branch. The adapter, cron bridge, handoff gate, observability, and source policy should be reviewable independently.

## Suggested implementation order for agents

1. Worker A implements envelope and identity mapping (Phase 1).
2. Worker B aligns Chronicle (JSON Schema + event-type catalogue) — runs in parallel with A (Phase 2 alignment).
3. Worker C migrates hooks to use envelope and Chronicle (Phase 3).
4. Worker D wraps cron logic behind a bridge (Phase 4).
5. Worker E adds handoff gate and approvals (Phase 5 + half of Phase 6).
6. Worker F adds observability bridge and cache policy (rest of Phase 6).
7. Source-policy unification (Phase 7) — can be owned by Worker A or a dedicated worker.
8. Worker G updates docs and checks consistency (Phase 8).
9. Orchestrator runs a final cross-cutting review.

## Review gates

A task is not merge-ready unless:

- tests pass (the machine is weak — run pytest sequentially, no parallelism — see memory `feedback_test_load`)
- new behaviour has contract tests
- redaction behaviour is tested
- docs are updated when public behaviour changes
- no raw user data is written to public traces or external observability
- no worker introduced a second scheduler or delivery authority
- no worker treated Gumi diegetic events as subject evidence
- no worker weakened existing OutputCritic behaviour
- no worker bypassed the existing `hermes-plugin` plugin loading contract

## Stop conditions for workers

Workers must stop and report instead of guessing when:

- a Hermes API shape is unclear
- a mapping from `sender_id` to `subject_id` is missing
- a change would require storing raw messages
- a test fixture needs real personal data
- a handoff would cross subject or profile boundaries
- a cron path would send a message without a Relic `DELIVER` decision
- an existing module (`relic/hermes_runtime.py`, `relic/hermes_plugin/*`, `relic/chronicle/*`, `relic/checkin/*`) would have to be rewritten rather than wrapped

## Minimum viable adapter (from current state)

The smallest useful next slice is:

1. `HermesRuntimeEnvelope` + identity mapping (Worker A)
2. Chronicle event-type catalogue + JSON Schema regeneration (Worker B)
3. Hook adapter emitting Chronicle events with canonical types (Worker C)
4. Cron bridge with `RuntimeDecisionResult` dataclass and Chronicle decision events (Worker D)
5. Handoff gate that blocks unsafe handoff by default (Worker E)

Approvals, observability, prompt cache, and source policy can land afterwards.

Do not start a Chronicle UI before the JSON Schema mirror is regenerated and the event-type catalogue is frozen.
