# Acceptance Tests

> **Revision 2026-05-16** — test layout updated to match the actual `tests/` tree. Existing suites are flagged as **LIVE**; suites to be added are flagged as **TO ADD**.

## Test suite layout

### LIVE (already in `master`)

```text
tests/chronicle/test_acceptance.py
tests/chronicle/test_access_audit.py
tests/chronicle/test_consent_gate.py
tests/chronicle/test_context.py
tests/chronicle/test_emitter.py
tests/chronicle/test_provenance.py
tests/chronicle/test_reader.py
tests/chronicle/test_redaction.py
tests/chronicle/test_retention.py
tests/chronicle/test_schema.py
tests/chronicle/test_snapshots.py
tests/hermes/test_checkpoint_contract.py
tests/hermes/test_delivery_gate.py
tests/hermes/test_no_agent_cron_mode_contract.py
tests/hermes/test_no_agent_cron_wiring.py
tests/hermes/test_platform_allowlist_contract.py
tests/hermes/test_resume_reconciliation.py
tests/hermes/test_rollback_flag_contract.py
tests/hermes/test_session_key_contract.py
tests/hermes/test_session_key_integration.py
tests/hermes/test_transform_llm_output_hook_contract.py
tests/hermes_compat/test_memory_user_snapshot_limits.py
tests/hermes_compat/test_no_soul_memory_user_mutation.py
tests/hermes_compat/test_one_provider_per_profile.py
tests/hermes_compat/test_plugin_context_injection.py
tests/hermes_compat/test_plugin_context_pack_ephemeral.py
tests/hermes_compat/test_plugin_failure_no_injection.py
tests/hermes_compat/test_relic_why_last_trace.py
tests/hermes_compat/test_soul_md_not_project_context.py
tests/hermes_plugin/test_bootstrap_script_redacted.py
tests/hermes_plugin/test_context_pack_ephemeral_not_system_prompt.py
tests/hermes_plugin/test_fail_safe.py
tests/hermes_plugin/test_inject_context_profile_fields.py
tests/hermes_plugin/test_no_soul_memory_user_mutation.py
tests/hermes_plugin/test_plugin_load.py
tests/hermes_plugin/test_pre_tool_call_blocks_side_effects.py
tests/hermes_plugin/test_relic_commands.py
tests/hermes_plugin/test_roleplay_cannot_trigger_side_effect_tool.py
tests/hermes_plugin/test_tool_permission_matrix.py
```

### TO ADD (adapter work)

```text
tests/hermes_compat/test_runtime_envelope.py
tests/hermes_compat/test_hook_trace_events.py
tests/hermes_compat/test_handoff_gate.py
tests/hermes_compat/test_approval_events.py
tests/hermes_compat/test_observability_redaction.py
tests/hermes_compat/test_prompt_cache_policy.py
tests/hermes_compat/test_source_policy.py
tests/hermes/test_cron_bridge_contract.py
tests/chronicle/test_event_types_catalogue.py        # Worker B alignment
```

Note: the original plan called for `tests/trace/*`. Chronicle absorbed that surface; the equivalent tests live under `tests/chronicle/*` and `tests/hermes/*`.

## Envelope tests — **TO ADD**

Target file: `tests/hermes_compat/test_runtime_envelope.py`.

Required cases:

1. Empty kwargs returns an envelope with no unsafe raw fields.
2. `HERMES_SESSION_ID` is used when explicit session is missing.
3. Explicit hook metadata overrides environment metadata.
4. `chat_id` is preserved as a redacted reference (`chat_ref`).
5. `sender_id` does not become `subject_id` without mapping.
6. Message text is hashed or referenced, not stored raw.
7. Envelope accepts a `session_key_hash` produced by `HermesSessionKey.derive` and binds the trace to it.

## Hook tests

### Existing behaviour to preserve — **LIVE**

Covered by `tests/hermes_compat/test_plugin_context_injection.py`, `test_plugin_context_pack_ephemeral.py`, `test_plugin_failure_no_injection.py`:

1. Empty subject returns `None`.
2. Missing session returns `None`.
3. Pre-LLM result is either `None` or `{"context": str}`.
4. Error dictionaries are never returned.
5. Injected context contains no `blocked_items` key.
6. Injected context contains no blocked reasons.
7. False physical experience claims are blocked or silenced (also covered by `tests/hermes/test_transform_llm_output_hook_contract.py`).
8. Clinical terms are blocked or rewritten.

### New behaviour — **TO ADD**

Target file: `tests/hermes_compat/test_hook_trace_events.py`.

1. Context pack request emits Chronicle event (`event_type="context_pack_requested"`).
2. Admitted context item emits Chronicle event (`event_type="context_item_admitted"`).
3. Blocked context item emits Chronicle event (`event_type="context_item_blocked"`) but is not injected.
4. Output rewrite emits Chronicle event (`event_type="output_rewritten"`).
5. Output silence emits Chronicle event (`event_type="output_silenced"`).
6. Trace event contains hashes and redacted summaries only (`payload_redacted=True`, no raw text).

## Cron bridge tests

### Existing — **LIVE**

`tests/hermes/test_no_agent_cron_mode_contract.py`, `test_no_agent_cron_wiring.py`, `test_delivery_gate.py`, `test_platform_allowlist_contract.py` already cover much of the cron and delivery surface.

### New contract — **TO ADD**

Target file: `tests/hermes/test_cron_bridge_contract.py`.

1. Subject opt-out returns `NO_REPLY` or `BLOCKED`, never `DELIVER`.
2. Quiet hours returns `BLOCKED`.
3. Platform not allowlisted returns `BLOCKED`.
4. Paused subject returns `BLOCKED`.
5. No due follow-up returns `NO_REPLY`.
6. Inside delivery window with due work can return `DELIVER`.
7. Media type selection respects policy and cooldown.
8. Every decision emits a Chronicle event with `event_type="delivery_decision_made"` and `payload.decision` matching the result.

## Handoff gate tests — **TO ADD**

Target file: `tests/hermes_compat/test_handoff_gate.py`.

1. Missing source session returns `BLOCK`.
2. Unknown target profile returns `BLOCK`.
3. Subject identity change returns `BLOCK`.
4. Policy snapshot change returns `REBUILD_CONTEXT` or `BLOCK`.
5. Correction revision change returns `REBUILD_CONTEXT` or `BLOCK`.
6. Low-risk model switch can return `ALLOW_REDUCED_CONTEXT`.
7. Explicitly allowed same-subject handoff can return `ALLOW_FULL_CONTEXT`.
8. Every result emits a Chronicle event with `event_type` in `{"handoff_requested","handoff_allowed","handoff_blocked"}`.

## Approval tests — **TO ADD**

Target file: `tests/hermes_compat/test_approval_events.py`.

1. Approval request is normalized into Chronicle event (`event_type="approval_requested"`).
2. Approval resolution links to request event via `parent_event_id`.
3. Denied approval blocks the action.
4. Approval event includes actor role and redacted action summary.
5. Approval event includes policy snapshot reference.

## Observability tests — **TO ADD**

Target file: `tests/hermes_compat/test_observability_redaction.py`.

1. External export span contains trace ID and decision code.
2. Export span contains no raw message text.
3. Export span contains no raw profile text.
4. Export span contains no raw correction text.
5. Export span contains no platform raw IDs.
6. Export failure does not corrupt local Chronicle trace.

## Prompt cache tests — **TO ADD**

Target file: `tests/hermes_compat/test_prompt_cache_policy.py`.

1. Static schema text can be cacheable (`STATIC_SAFE`).
2. Current subject profile text is not cacheable by default.
3. Recent continuity markers are not cacheable.
4. Cache key must include `profile_snapshot_id` for profile-bearing content.
5. Cache key must include `policy_snapshot_id` for policy-bearing content.
6. Cache key must include `correction_revision`.
7. Missing invalidation keys cause cache refusal.

## Source policy tests — **TO ADD**

Target file: `tests/hermes_compat/test_source_policy.py`.

1. `USER_DIRECT_MESSAGE` is evidence-eligible by default (subject to consent).
2. `GUMI_DIEGETIC_EVENT` is not evidence-eligible by default.
3. `GUMI_GENERATED_MEDIA` does not update subject model alone.
4. `PUBLIC_WEB_SOURCE` requires explicit user request.
5. Classification emits Chronicle event with `event_type="source_policy_checked"` and `payload.source_class`.
6. `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py` consult the taxonomy (regression test).

## Event-type catalogue tests — **TO ADD**

Target file: `tests/chronicle/test_event_types_catalogue.py`.

1. Catalogue constants in `relic/chronicle/event_types.py` (or equivalent) export every event type used by adapter modules.
2. Each adapter-emitted `event_type` matches a catalogue constant.
3. JSON Schema `schemas/relic_trace_event.schema.json` enumerates the catalogue values (or is regenerated from the Pydantic model and the catalogue).

## Redaction regression strings

Use synthetic strings that must never appear in exported traces:

```text
RAW_USER_SECRET_SENTENCE_7f3a
RAW_PROFILE_PRIVATE_NOTE_2b91
RAW_CORRECTION_TEXT_a81c
RAW_PLATFORM_ID_99aa
RAW_MEDIA_PROMPT_42cc
```

Tests should inject these strings into input fixtures and assert that they do not appear in:

- Chronicle JSONL payloads when raw storage is disabled
- Chronicle SQLite payloads when raw storage is disabled
- observability export payloads
- context injection strings if blocked
- error messages sent to Hermes

Reference: `relic/chronicle/redaction.py::redact_payload`, `contains_secret`. Existing coverage in `tests/chronicle/test_redaction.py`.

## CLI checks

Existing suites:

```bash
pytest tests/chronicle/ -p no:xdist
pytest tests/hermes/ -p no:xdist
pytest tests/hermes_compat/ -p no:xdist
pytest tests/hermes_plugin/ -p no:xdist
```

New suites (once added):

```bash
pytest tests/hermes_compat/test_runtime_envelope.py
pytest tests/hermes_compat/test_hook_trace_events.py
pytest tests/hermes_compat/test_handoff_gate.py
pytest tests/hermes_compat/test_approval_events.py
pytest tests/hermes_compat/test_observability_redaction.py
pytest tests/hermes_compat/test_prompt_cache_policy.py
pytest tests/hermes_compat/test_source_policy.py
pytest tests/hermes/test_cron_bridge_contract.py
pytest tests/chronicle/test_event_types_catalogue.py
```

Full suite:

```bash
pytest -p no:xdist
```

Note: the local machine is constrained — run `pytest` **sequentially**, no parallelism, to avoid crashes. (See user memory `feedback_test_load`.)

## Merge readiness checklist

A branch is merge-ready only when:

- all changed public behaviour has tests
- all tests pass locally (sequentially)
- redaction tests pass
- no raw synthetic secret appears in trace or observability output
- existing Hermes plugin compatibility is preserved (`tests/hermes_compat/test_plugin_*`)
- existing Hermes contract suites stay green (`tests/hermes/*`)
- Chronicle suite stays green (`tests/chronicle/*`)
- docs are updated
- schema examples validate against the regenerated `relic_trace_event.schema.json`
- no new runtime path can deliver a proactive message without a Relic decision
