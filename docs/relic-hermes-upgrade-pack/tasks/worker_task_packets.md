# Worker Task Packets

> **Revision 2026-05-16** — packets reframed as **forward-port from current state**. Original Task B1 (build trace ledger) is retired because Chronicle already exists; a smaller alignment packet (B2) replaces it.

## Task A1: Add HermesRuntimeEnvelope and identity mapping

Owner: Worker A

Status: **OPEN**

Objective: Add a normalized, redaction-safe runtime envelope for Hermes metadata and a separate identity mapper.

Files to inspect:

```text
hermes-plugin/tools/relic_shared_continuity/hooks.py
relic/hermes_runtime.py                       (HermesSessionKey, pass_session_key, render_subject_hermes_config)
tests/hermes_compat/test_plugin_context_injection.py
tests/hermes/test_session_key_contract.py
schemas/hermes/session_key.schema.json
docs/03-contracts-and-schemas.md              (this pack — Runtime envelope contract)
schemas/hermes_runtime_envelope.schema.json   (this pack — forward-target)
```

Files to create:

```text
relic/hermes_adapter/__init__.py
relic/hermes_adapter/envelope.py
relic/hermes_adapter/identity.py
schemas/hermes/runtime_envelope.schema.json   (promote pack schema into live tree)
tests/hermes_compat/test_runtime_envelope.py
```

Expected behaviour:

- Build envelope from kwargs, `hook_ctx` dict/object, and `HERMES_SESSION_ID`.
- Prefer explicit values over environment values.
- Hash or redact sender and channel identifiers.
- Do not store raw message text in the envelope by default.
- Generate a `trace_id` when missing (UUID4).
- Accept a `session_key_hash` from `HermesSessionKey.derive` and bind it.
- `identity.py::resolve_subject(envelope)` returns `subject_ref` only if explicit mapping or configured fallback allows it; otherwise returns `None`.

Tests:

- empty metadata
- env session fallback
- explicit session override
- chat ID extraction
- sender ID redaction
- no raw message text stored
- session_key_hash binding
- identity resolution refuses unmapped sender → subject promotion

Acceptance criteria:

- `pytest tests/hermes_compat/test_runtime_envelope.py -p no:xdist` passes.
- Envelope sample validates against `schemas/hermes/runtime_envelope.schema.json`.
- No existing test in `tests/hermes_compat/`, `tests/hermes/`, `tests/hermes_plugin/` regresses.

Stop conditions:

- `relic/hermes_runtime.py` does not expose enough of the session-key contract to bind the envelope without modification.
- Hermes hook metadata shape cannot be inferred from `hermes-plugin/tools/relic_shared_continuity/hooks.py`.

## Task B2: Chronicle alignment (replaces original B1)

Owner: Worker B

Status: **OPEN**

Objective: Align Chronicle (already shipped) with the pack contracts — freeze a canonical event-type catalogue and regenerate the JSON Schema mirror from the Pydantic source-of-truth.

> Note: Original Task B1 ("build RelicTraceEvent and JSONL sink") is **retired**. Chronicle (`relic/chronicle/`) already provides Events, Decisions, StateSnapshots, ProvenanceEdges, AccessLog, redaction, consent gate, retention reaper. Do not build a parallel trace system.

Files to inspect:

```text
relic/chronicle/schema.py
relic/chronicle/emitter.py
relic/chronicle/enums.py
relic/chronicle/redaction.py
relic/db/migrations/0003_chronicle_events.sql
schemas/relic_trace_event.schema.json         (this pack — forward-target, currently divergent)
docs/03-contracts-and-schemas.md              (event-type catalogue list)
```

Files to create:

```text
relic/chronicle/event_types.py                (canonical event-type constants)
schemas/chronicle/event.schema.json           (generated from Event Pydantic model)
tests/chronicle/test_event_types_catalogue.py
```

Files to update:

```text
docs/relic-hermes-upgrade-pack/schemas/relic_trace_event.schema.json
  → either regenerate from Pydantic Event model or mark as RETIRED in favour of schemas/chronicle/event.schema.json
```

Expected behaviour:

- `relic/chronicle/event_types.py` exports string constants for every event type listed in `docs/03-contracts-and-schemas.md` (runtime / governance / model output / profile / observability groups).
- JSON Schema generator script (`scripts/generate_chronicle_schemas.py` or similar) produces `schemas/chronicle/event.schema.json` from the Pydantic model.
- Test asserts every catalogue constant matches the Pydantic `event_type` regex.
- Test asserts a sample Event validates against the generated JSON Schema.

Acceptance criteria:

- `pytest tests/chronicle/test_event_types_catalogue.py -p no:xdist` passes.
- Generated JSON Schema validates every existing `tests/chronicle/fixtures/*` sample.
- No regression in `tests/chronicle/*`.

Stop conditions:

- `relic/chronicle/schema.py::Event` requires field changes (out of scope for this packet — escalate to orchestrator).

## Task C1: Migrate Hermes hooks to adapter implementation

Owner: Worker C

Dependencies: A1, B2

Status: **OPEN**

Objective: Keep the Hermes-loadable entrypoint stable while moving the implementation into `relic.hermes_adapter.hooks`, and emit Chronicle events for the new touchpoints.

Files to inspect:

```text
hermes-plugin/tools/relic_shared_continuity/hooks.py    (current 212-LoC implementation)
relic/gumi_continuity/admission.py
relic/context_pack/render.py
relic/shared_continuity/service.py
relic/gumi_plugin/critic.py
relic/patterns/signal_extractor.py
relic/safety/escalation_notifier.py
tests/hermes_compat/test_plugin_context_injection.py
tests/hermes_compat/test_plugin_context_pack_ephemeral.py
tests/hermes_compat/test_plugin_failure_no_injection.py
```

Files to change/create:

```text
relic/hermes_adapter/hooks.py
hermes-plugin/tools/relic_shared_continuity/hooks.py    (reduce to thin shim)
tests/hermes_compat/test_hook_trace_events.py
```

Expected behaviour:

- Public hook functions remain available (`pre_llm_call`, `post_llm_call`, `transform_llm_output`).
- Implementation moves to `relic.hermes_adapter.hooks` and consumes a `HermesRuntimeEnvelope`.
- Pre-LLM hook returns only `None` or `{"context": str}`.
- Blocked items are emitted as Chronicle events (`context_item_blocked`) but never injected.
- Output critic behaviour is preserved — fall-through to clinical-term filter remains intact.
- Hook failures do not leak error dicts into Hermes (`pre_llm_call` keeps its `try/except` fail-closed wrapper).
- Safety scan in the `finally` block of `pre_llm_call` is preserved.
- `chat_id` from `hook_ctx` is read into the envelope.

Tests:

- existing `tests/hermes_compat/test_plugin_*` keep passing
- new Chronicle event assertions:
  - `context_pack_requested` on every call
  - `context_item_admitted` per admitted marker
  - `context_item_blocked` per blocked decision
  - `output_rewritten` when critic replaces text
  - `output_silenced` when critic returns `[SILENT]`
  - `output_passed` otherwise
- emitted events have `payload_redacted=True` and `payload_hash` set; no raw message text in payload

Acceptance criteria:

- `pytest tests/hermes_compat/test_plugin_context_injection.py tests/hermes_compat/test_hook_trace_events.py -p no:xdist` passes.
- Hermes plugin loader still picks up `hermes-plugin/tools/relic_shared_continuity/hooks.py` (verify via `tests/hermes_plugin/test_plugin_load.py`).

Stop conditions:

- Moving the implementation would break Hermes plugin loading and no compatibility wrapper is possible.
- Envelope shape from Task A1 is missing a field required by the existing hook (escalate).

## Task D1: Add cron bridge

Owner: Worker D

Dependencies: A1, B2

Status: **OPEN**

Objective: Make Hermes cron/watchers call Relic decision logic through a structured bridge.

Files to inspect:

```text
relic/gumi_plugin/cron_wiring.py
relic/checkin/scheduler.py
relic/hermes_runtime.py                       (RuntimeDecision enum, RuntimeDecisionReason, DeliveryGate)
schemas/hermes/no_agent_cron_mode.schema.json
schemas/hermes/delivery_gate.schema.json
tests/hermes/test_no_agent_cron_mode_contract.py
tests/hermes/test_no_agent_cron_wiring.py
tests/hermes/test_delivery_gate.py
tests/hermes/test_platform_allowlist_contract.py
```

Files to create/change:

```text
relic/hermes_adapter/cron_bridge.py
tests/hermes/test_cron_bridge_contract.py
```

Expected behaviour:

- Expose `evaluate_no_agent_tick(envelope: HermesRuntimeEnvelope) -> RuntimeDecisionResult`.
- `RuntimeDecisionResult` dataclass with fields per `docs/03-contracts-and-schemas.md` (Cron decision contract).
- `decision` field reuses `relic.hermes_runtime.RuntimeDecision` enum.
- `reason_codes` reuses `relic.hermes_runtime.RuntimeDecisionReason` values.
- Reuse existing quiet hours, platform allowlist, paused subject, due follow-up, delivery window rules.
- Call `DeliveryGate.enforce(target_platform)` before producing `DELIVER`.
- Emit Chronicle event for every decision (`event_type="delivery_decision_made"`, payload includes decision + reason codes).
- `trace_event_id` field is the Chronicle `event_id`.

Tests:

- opt-out → `NO_REPLY` or `BLOCKED`
- quiet hours → `BLOCKED`
- platform not allowlisted → `BLOCKED`
- paused subject → `BLOCKED`
- no due work → `NO_REPLY`
- deliver inside allowed window with due work → `DELIVER`
- media-type selection respects cooldown
- every decision emits Chronicle event

Acceptance criteria:

- `pytest tests/hermes/test_cron_bridge_contract.py tests/hermes/test_no_agent_cron_wiring.py tests/hermes/test_delivery_gate.py -p no:xdist` passes.
- No code path returns `DELIVER` when the delivery gate denies.

Stop conditions:

- `relic/checkin/scheduler.py` and `relic/gumi_plugin/cron_wiring.py` overlap in a way that requires deduplication beyond the scope of this packet (escalate).

## Task E1: Add handoff gate

Owner: Worker E

Dependencies: A1, B2

Status: **OPEN**

Objective: Gate Hermes `/handoff` through Relic policy.

Files to inspect:

```text
relic/hermes_runtime.py
relic/gumi_plugin/critic.py
relic/correction/                             (correction state for rebuild checks)
docs/03-contracts-and-schemas.md              (Handoff contract)
```

Files to create:

```text
relic/hermes_adapter/handoff_gate.py
tests/hermes_compat/test_handoff_gate.py
```

Expected behaviour:

- Evaluate source session, target profile, policy snapshot, profile snapshot, correction revision, risk boundary.
- Return `ALLOW_FULL_CONTEXT`, `ALLOW_REDUCED_CONTEXT`, `REBUILD_CONTEXT`, or `BLOCK`.
- `HandoffDecision` dataclass per contract.
- Emit Chronicle event for every request and result (`handoff_requested`, `handoff_allowed`, `handoff_blocked`).
- Default to `BLOCK` when evaluation fails.

Tests per `docs/04-acceptance-tests.md` § Handoff gate tests.

Acceptance criteria:

- Handoff cannot preserve stale context after correction changes.
- Handoff result includes `trace_event_id` matching a Chronicle event.

Stop conditions:

- Target profile semantics are not represented anywhere in current code (escalate — likely requires a profile registry).

## Task E2: Add approval normalization

Owner: Worker E (sibling to E1)

Dependencies: A1, B2

Status: **OPEN**

Objective: Normalize Hermes approval events into Chronicle events.

Files to create:

```text
relic/hermes_adapter/approvals.py
tests/hermes_compat/test_approval_events.py
```

Expected behaviour per `docs/03-contracts-and-schemas.md` (Approval section).

Tests per `docs/04-acceptance-tests.md` § Approval tests.

Stop conditions:

- No stable way exists to access approval events from Hermes in the current installed version (escalate).

## Task F1: Add observability bridge

Owner: Worker F

Dependencies: A1, B2

Status: **OPEN**

Objective: Export redacted observability summaries to Hermes / Langfuse.

Files to create:

```text
relic/hermes_adapter/observability.py
tests/hermes_compat/test_observability_redaction.py
```

Expected behaviour per `docs/03-contracts-and-schemas.md` (Observability export contract).

Tests per `docs/04-acceptance-tests.md` § Observability tests, using the synthetic regression strings.

Acceptance criteria:

- Raw synthetic strings never appear in external span payload.
- Export failure does not corrupt local Chronicle trace.

## Task F2: Add prompt cache safety policy

Owner: Worker F

Dependencies: A1

Status: **OPEN**

Objective: Classify prompt sections and enforce invalidation rules.

Files to create:

```text
relic/hermes_adapter/prompt_cache.py
tests/hermes_compat/test_prompt_cache_policy.py
```

Expected behaviour per `docs/03-contracts-and-schemas.md` (Cache contract).

Tests per `docs/04-acceptance-tests.md` § Prompt cache tests.

Stop conditions:

- Prompt section boundaries are not represented in code and cannot be introduced without touching unrelated prompt rendering (escalate).

## Task H1: Source policy unification

Owner: Worker A or dedicated worker

Dependencies: A1

Status: **OPEN (new)**

Objective: Single source-class taxonomy enforced at the runtime boundary.

Files to inspect:

```text
relic/gumi_continuity/admission.py
relic/gumi_plugin/admission.py
relic/context_pack/                           (where admission is consumed)
docs/03-contracts-and-schemas.md              (Source policy contract)
```

Files to create:

```text
relic/hermes_adapter/source_policy.py
tests/hermes_compat/test_source_policy.py
```

Expected behaviour:

- Enum of source classes per contract.
- `classify(envelope) -> SourceClass`.
- `is_evidence_eligible(source_class, consent_state) -> bool`.
- Existing admission modules consult the taxonomy.
- Emit Chronicle event `source_policy_checked` per classification.

Tests per `docs/04-acceptance-tests.md` § Source policy tests.

Stop conditions:

- Migrating both admission modules to the taxonomy in one packet is too large — split into H1a (taxonomy + tests) and H1b (admission consumer migration).

## Task G1: Documentation update

Owner: Worker G

Dependencies: A1 to H1

Status: **PARTIAL → OPEN**

Objective: Document the new integration surface in the main docs tree.

Files to create/change:

```text
docs/architecture/hermes-current-state.md     (audit snapshot — small, written first)
docs/architecture/hermes-integration.md       (update existing — describe adapter surface)
docs/architecture/trace-ledger.md             (new — Chronicle for outside readers)
docs/guides/hermes-v2026-5-16-upgrade.md      (new — migration notes for adopters)
docs/reference/hermes-adapter.md              (new — module-by-module API reference)
CHANGELOG.md                                   (new entry)
```

Expected content:

- runtime boundary (linked to ADR-001)
- adapter package map (with `hermes_runtime.py` + `hermes_plugin/` + `chronicle/` cross-references)
- Chronicle event types (linked to `relic/chronicle/event_types.py`)
- redaction rules
- cron bridge behaviour
- handoff gate behaviour
- cache safety policy
- migration notes

Acceptance criteria:

- Docs match implemented APIs.
- Docs mention that Langfuse is not the Relic audit source of record.
- Docs mention that Gumi diegetic events are not subject evidence by default.
- `mkdocs build` succeeds with no broken links.
