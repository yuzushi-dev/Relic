# Contracts and Schemas

> **Revision 2026-05-16** — contracts unchanged in shape. Each contract now lists its **status** (LIVE / PARTIAL / GAP) and points at the actual module that hosts (or should host) it.

## Boundary contract

Hermes is allowed to provide:

- runtime session metadata
- gateway and chat metadata
- hook context
- tool execution context
- approval stream events
- scheduler and watcher ticks
- model/provider execution surface
- operational trace sinks

Relic is allowed to decide:

- whether a source is eligible for ingestion
- whether a subject mapping is valid
- whether context can be injected
- which context items are admitted or blocked
- whether an output is allowed, rewritten, or silenced
- whether proactive delivery is allowed
- whether handoff is allowed
- whether an event becomes evidence
- whether a profile can be updated

Hermes must not decide profile truth. Relic must not become a platform gateway.

## Runtime envelope contract — **GAP**

Target module: `relic/hermes_adapter/envelope.py`
Schema (forward-target): `schemas/hermes_runtime_envelope.schema.json` (this pack) — promote to `schemas/hermes/runtime_envelope.schema.json` when implementation lands.
Existing related code: `relic/hermes_runtime.py::HermesSessionKey`, `pass_session_key`.

A `HermesRuntimeEnvelope` is a normalized, redaction-safe object created from Hermes runtime metadata.

Minimum fields:

```text
schema_version
trace_id
session_id
chat_id
platform
channel_ref
sender_ref
subject_ref
hermes_profile_id
gumi_instance_id
model
turn_index
tool_call_id
message_ref
message_hash
received_at
metadata_redaction_status
```

Rules:

- `session_id` can come from `hook_ctx`, explicit kwargs, or `HERMES_SESSION_ID`.
- `chat_id` can come from `hook_ctx` when available — current hooks do not read it; envelope work must.
- `sender_id` must be converted to `sender_ref` before trace export.
- `subject_ref` requires explicit mapping or a local configured fallback. Current `hooks.py` uses `subject_id = sender_id or session_id` — that fallback must move into `identity.py` and be flagged as `metadata_redaction_status="raw_allowed"` only when explicit configuration enables it.
- Raw message text is not part of the envelope by default.
- Message hashes must be stable enough for debugging but not reversible.
- Envelope must accept a `session_key_hash` (from `HermesSessionKey.derive`) for binding.

## Trace event contract — **LIVE (as Chronicle); JSON Schema PARTIAL**

Source of truth: `relic/chronicle/schema.py::Event` (Pydantic).
Schema mirror (forward-target): `schemas/relic_trace_event.schema.json` (this pack) — must be regenerated from the Pydantic model before being used to validate samples.
Storage: dual-write JSONL (`~/.relic/chronicle/journal/{YYYY-MM-DD}.jsonl`) + SQLite (migrations `0003`–`0007`).

A Chronicle `Event` is append-only. It records a governed decision, state transition, or observed runtime event.

Chronicle-mandatory fields (see `Event` Pydantic model):

```text
event_id            (UUID, default new)
event_type          (snake_case string, regex-validated)
event_category      (EventCategory enum)
trace_id            (UUID)
run_id              (UUID | None)
session_id          (UUID | None)
parent_event_id     (UUID | None)
experiment_id       (UUID | None)
subject_id          (string | None)
agent_id            (string | None)
profile_id          (string | None)
hermes_profile_id   (string | None)
actor_type          (string | None)
actor_id            (string | None)
source_module       (string, required)
target_module       (string | None)
timestamp           (UTC ISO string)
duration_ms         (float | None)
input_refs          (list[str])
output_refs         (list[str])
payload_redacted    (bool, default False)
payload_hash        (sha256:<16-64 hex> | None)
payload             (dict, default {})
sensitivity         (PrivacyLevel enum)
visibility          (VisibilityLevel enum)
consent_basis       (string | None)
retention_policy    (RetentionPolicy enum)
tags                (list[str], "key:value" format)
severity            (string, default "info")
validation_status   (string | None)
error_code          (string | None)
retry_count         (int)
schema_version      ("chronicle-event/v1")
created_at          (UTC ISO string)
```

Companion record types (also LIVE): `Decision`, `StateSnapshot`, `ProvenanceEdge`, `AccessLogEntry`.

### Event-type catalogue — **PARTIAL**

`Event.event_type` is a free snake_case string. Adapter modules must emit a canonical vocabulary so traces remain queryable.

Runtime:

```text
runtime_received
identity_resolved
tool_call_observed
approval_requested
approval_resolved
```

Governance:

```text
source_policy_checked
context_pack_requested
context_item_admitted
context_item_blocked
context_pack_rendered
handoff_requested
handoff_allowed
handoff_blocked
delivery_decision_made
```

Model output:

```text
llm_call_prepared
llm_output_received
llm_output_reviewed
output_rewritten
output_silenced
output_passed
```

Profile and correction:

```text
evidence_observed
signal_extracted
profile_snapshot_created
correction_requested
correction_applied
correction_rejected
```

Observability:

```text
observability_export_requested
observability_exported
observability_export_blocked
```

Worker B owns freezing this catalogue (recommended location: `relic/chronicle/event_types.py`).

## Context injection contract — **LIVE**

Source: `hermes-plugin/tools/relic_shared_continuity/hooks.py::pre_llm_call`.

Pre-LLM context injection may return only:

```python
None
{"context": "...redacted admitted context..."}
```

It must not return:

```python
{"error": "..."}
{"fail_closed": True}
{"blocked_items": [...]}
```

Blocked items must be represented only in Chronicle events and local audit state, never in injected prompt context.

Verified by `tests/hermes_compat/test_plugin_failure_no_injection.py`, `test_plugin_context_pack_ephemeral.py`, `test_plugin_context_injection.py`.

## Output critic contract — **LIVE**

Source: `relic/gumi_plugin/critic.py::OutputCritic` + `hermes-plugin/tools/relic_shared_continuity/hooks.py::transform_llm_output`.

The output critic may return:

```python
None
"[SILENT]"
"replacement text"
```

Rules:

- `None` means pass-through.
- `[SILENT]` means the output must not be sent.
- Replacement text must avoid clinical labels, false lived experience, dependency escalation, and system-detection claims.
- Any output rewrite or silence must create a Chronicle event (currently it does not — Phase 3 work).

Current critic verdict reasons (from code): `false_physical_experience` → `[SILENT]`; `dependency` / `need` → neutral redirect. Fallback term filter uses `FORBIDDEN_OUTPUT_TERMS` list in `hooks.py`.

## Cron decision contract — **PARTIAL**

Target module: `relic/hermes_adapter/cron_bridge.py` (GAP).
Existing related code: `relic/hermes_runtime.py::RuntimeDecision` (Enum), `relic/hermes_runtime.py::DeliveryGate`, `relic/gumi_plugin/cron_wiring.py`, `relic/checkin/scheduler.py`.

Relic cron bridge returns:

```python
@dataclass
class RuntimeDecisionResult:
    decision: RuntimeDecision   # reuse the existing enum from relic.hermes_runtime
    reason_codes: list[str]
    subject_ref: str
    hermes_profile_id: str | None
    gumi_instance_id: str | None
    candidate_message: str | None
    media_type: Literal["text", "voice", "image", "music"] | None
    trace_event_id: str
```

`RuntimeDecision` values (already in code): `NO_REPLY`, `CANDIDATE`, `DELIVER`, `BLOCKED`, `ERROR`.

Rules:

- `DELIVER` is the only decision Hermes may send.
- `CANDIDATE` must still pass a delivery gate (`DeliveryGate.enforce`).
- `NO_REPLY` should still be traced (Chronicle event).
- `BLOCKED` should include `reason_codes` (reuse `relic/hermes_runtime.py::RuntimeDecisionReason`).
- `ERROR` should not expose exception text to user-facing channels.

## Handoff contract — **GAP**

Target module: `relic/hermes_adapter/handoff_gate.py`.

Relic handoff gate returns:

```python
@dataclass
class HandoffDecision:
    result: Literal[
        "ALLOW_FULL_CONTEXT",
        "ALLOW_REDUCED_CONTEXT",
        "REBUILD_CONTEXT",
        "BLOCK",
    ]
    reason_codes: list[str]
    source_session_id: str
    target_profile_id: str | None
    policy_snapshot_id: str | None
    profile_snapshot_id: str | None
    trace_event_id: str
```

Default stance:

- If the gate cannot evaluate, return `BLOCK`.
- If correction state changed, return `REBUILD_CONTEXT` or `BLOCK`.
- If subject mapping changes, return `BLOCK`.
- If target mode increases intimacy or proactivity, require explicit policy allowance.

## Observability export contract — **GAP**

Target module: `relic/hermes_adapter/observability.py`.

External observability gets only:

- event IDs
- trace IDs
- durations
- status codes
- decision codes
- model names
- tool names
- redaction status
- payload hashes
- schema versions

External observability must not receive:

- raw user messages
- raw subject profiles
- raw correction text
- raw clinical/safety phrases
- private Gumi media prompts
- unredacted platform identifiers
- full context packs

Chronicle remains the audit source of record. Langfuse remains an operational debugging surface.

## Cache contract — **GAP**

Target module: `relic/hermes_adapter/prompt_cache.py`.

A cached prompt section must be classified as one of:

```text
STATIC_SAFE
POLICY_VERSIONED
PROFILE_VERSIONED
NEVER_CACHE
```

Rules:

- Current profile text is `NEVER_CACHE` unless stored as a short-lived versioned block with full invalidation keys.
- Recent continuity markers are `NEVER_CACHE`.
- Static schema text can be `STATIC_SAFE`.
- Policy text can be `POLICY_VERSIONED`.
- Any cache key missing correction revision is invalid for profile-bearing prompts.

Invalidation keys:

```text
profile_snapshot_id
policy_snapshot_id
correction_revision
context_pack_hash
admission_policy_version
output_critic_version
subject_status
```

## Source policy contract — **GAP (admission split today)**

Target module: `relic/hermes_adapter/source_policy.py`.
Existing related code: `relic/gumi_continuity/admission.py`, `relic/gumi_plugin/admission.py`.

Every incoming source must be classified before it can become evidence.

Source classes:

```text
USER_DIRECT_MESSAGE
USER_EXPLICIT_CORRECTION
USER_APPROVAL
USER_REACTION_TO_GUMI
GUMI_DIEGETIC_EVENT
GUMI_GENERATED_MEDIA
SYSTEM_EVENT
TOOL_OUTPUT
PUBLIC_WEB_SOURCE
SCHEDULED_WATCHER_SOURCE
```

Default eligibility:

| Source class                  | Evidence eligible by default | Notes                                                            |
|-------------------------------|---:|------------------------------------------------------------------|
| `USER_DIRECT_MESSAGE`         | yes | Subject to consent and retention policy                          |
| `USER_EXPLICIT_CORRECTION`    | yes | Higher priority than inferred state                              |
| `USER_APPROVAL`               | yes | Narrow scope, approval only                                      |
| `USER_REACTION_TO_GUMI`       | yes | Must reference user response, not Gumi event alone               |
| `GUMI_DIEGETIC_EVENT`         | no  | Can be relationship context, not subject evidence                |
| `GUMI_GENERATED_MEDIA`        | no  | Never updates subject model alone                                |
| `SYSTEM_EVENT`                | no  | Runtime audit only unless explicitly mapped                      |
| `TOOL_OUTPUT`                 | no  | Requires tool-specific policy                                    |
| `PUBLIC_WEB_SOURCE`           | no  | Requires explicit user request and provenance                    |
| `SCHEDULED_WATCHER_SOURCE`    | no  | Runtime trigger only unless admitted                             |

Adapter must funnel `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py` decisions through `classify(envelope) -> SourceClass` so that the eligibility table is enforced in one place.

## Session-key contract — **LIVE**

Source: `relic/hermes_runtime.py::HermesSessionKey`, `pass_session_key`. Schema `schemas/hermes/session_key.schema.json`.

Rules (already enforced):

- Session key derived from `(subject_id, gumi_instance_id, hermes_profile_id)`.
- Only the hash is stored; raw key never persisted.
- Cross-subject session keys are rejected.
- Missing scope is rejected.

Adapter envelope should accept the hash as input to bind tool calls to a Relic trace.

## Delivery gate contract — **LIVE**

Source: `relic/hermes_runtime.py::DeliveryGate`, `DeliveryGateDecision`, allowlist store helpers. Schema `schemas/hermes/delivery_gate.schema.json`, `schemas/hermes/platform_allowlist.schema.json`.

Rules (already enforced):

- Per-`(subject_id, platform)` allowlist entries.
- `check(target_platform, subject_id)` returns a `DeliveryGateDecision`.
- `enforce(target_platform)` returns `(decision, event)` with a `DeliveryGateDecisionEvent` for audit.

Cron bridge must call `DeliveryGate.enforce` before producing a `RuntimeDecisionResult` of `DELIVER`.
