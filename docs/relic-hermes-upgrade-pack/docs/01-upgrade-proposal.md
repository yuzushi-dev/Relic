# Proposal: Upgrade Relic for Hermes v2026.5.16 Integration

> **Revision 2026-05-16** — original proposal aligned to actual codebase state. Boundary architecture unchanged. Module paths and trace ledger design reconciled to what was built.

## Executive summary

Relic should not absorb Hermes features wholesale. The chosen design is a **boundary upgrade**.

Hermes is the runtime carrier: sessions, gateways, tool execution, plugin lifecycle, approvals, cron/watchers, delivery surfaces, external observability.

Relic is the governance and modeling layer: subject identity, evidence admission, context pack construction, policy snapshots, correction state, trace artifacts, output criticism, proactive decision logic, audit rules.

The original plan proposed a `relic.hermes_adapter` package. Implementation evolved into a **distributed adapter surface**: `relic/hermes_runtime.py` (session keys, delivery gate, runtime decision enum, render configs), `relic/hermes_plugin/` (commands, context injection, fail-safe, plugin lifecycle, tool permissions), `relic/gumi_plugin/cron_wiring.py` (no-agent cron decisions), `relic/checkin/scheduler.py` (check-in scheduling), and the upstream `hermes-plugin/tools/relic_shared_continuity/` entrypoint.

The trace ledger landed as **Chronicle** (`relic/chronicle/`) rather than a thin `relic/trace/` JSONL sink. Chronicle dual-writes JSONL + SQLite, covers events + decisions + state snapshots + provenance edges + access log, and ships with redaction, consent gate, retention reaper, and an access-audit layer. Migrations `0003`–`0007` provide the schema.

This revision keeps the contracts (envelope shape, decision shape, handoff shape, source policy) but maps each one to either an existing module or an explicit gap to be filled.

## Current Relic baseline (verified)

Verified files in `master` as of 2026-05-16:

- `hermes-plugin/tools/relic_shared_continuity/hooks.py` — 212 LoC, implements `pre_llm_call`, `transform_llm_output`, `post_llm_call`. Directly imports `relic.gumi_continuity.admission`, `relic.context_pack.*`, `relic.shared_continuity.service`, `relic.patterns.signal_extractor`, `relic.safety.escalation_notifier`, `relic.gumi_plugin.critic`. Fail-closed wrapper present. No adapter indirection.
- `relic/hermes_runtime.py` — 715 LoC. Defines `HermesSessionKey`, `pass_session_key`, `DeliveryGateDecision`, `DeliveryGateDecisionEvent`, `DeliveryGate`, `RuntimeDecision`, `RuntimeDecisionReason`, `DecisionEvent`, allowlist store helpers, `render_hindsight_local_config`, `render_subject_hermes_config`.
- `relic/hermes_plugin/` — `commands.py`, `context_injection.py`, `fail_safe.py`, `hooks.py`, `memory_provider.py`, `plugin.py`, `resume_hooks.py`, `soul_loader.py`, `tool_permissions.py`.
- `relic/gumi_plugin/cron_wiring.py` — no-agent cron decision logic, quiet hours, delivery windows, proactive check-in, media selection.
- `relic/checkin/` — new module: `scheduler.py`, `question_engine.py`, `facet_updater.py`, `anti_repeat.py`, `db_init.py`.
- `relic/chronicle/` — `emitter.py`, `reader.py`, `schema.py`, `enums.py`, `context.py`, `redaction.py`, `consent_gate.py`, `retention.py`, `access_audit.py`, `snapshots.py`, `provenance.py`, `cli/`, `adapters/legacy_jsonl.py`.
- Migrations `0003_chronicle_events.sql`, `0004_chronicle_decisions.sql`, `0005_chronicle_state_snapshots.sql`, `0006_chronicle_provenance_edges.sql`, `0007_chronicle_access_log.sql`.
- Tests: `tests/chronicle/` (12 files), `tests/hermes/` (10 contract files), `tests/hermes_compat/` (8 files), `tests/hermes_plugin/` (10 files).
- Schemas in `schemas/hermes/`: `checkpoint`, `delivery_gate`, `no_agent_cron_mode`, `platform_allowlist`, `rollback_flag`, `session_key`, `transform_llm_output_hook`.
- Existing docs: `docs/guides/hermes-integration.md` plus the upgrade pack itself.

The upgrade is therefore **evolutionary** with significant work already landed on the trace and runtime-decision sides, and the integration boundary still to be formalised on the envelope / handoff / approvals / observability / cache axes.

## Hermes v2026.5.16 features to use

The release-note features remain the integration surface. The "Relic use" column is unchanged; the "Where it lands" column is new.

| Hermes feature                                | Relic use                                                        | Where it lands today (or where it should land)                                                  |
|-----------------------------------------------|------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| `/handoff` live session transfer              | Move running session between model/persona/profile               | **GAP** — `handoff_gate` not implemented. Add `relic/hermes_adapter/handoff_gate.py` or `relic/control/handoff_gate.py`. |
| `ctx.llm` inside plugins                      | Classification, context-pack review, critic support              | `relic/gumi_plugin/critic.py` (OutputCritic) already used. Provide adapter access pattern.       |
| `tool_override`                               | Governed wrappers when Relic must enforce source policy          | `relic/hermes_plugin/tool_permissions.py` already gates tools.                                  |
| `HERMES_SESSION_ID` exposed to tools          | Bind tool calls to Relic trace                                   | **PARTIAL** — `HermesSessionKey` derives a scoped hash; envelope-level binding still missing.   |
| `chat_id` in `hook_ctx`                       | Disambiguate platform thread/channel                             | **GAP** — `hooks.py` does not read `chat_id`.                                                   |
| Approval events in API stream                 | Trace long-running actions and human approvals                   | **GAP** — no `approvals.py`. Chronicle has emitter slots but no normalization adapter.          |
| Langfuse observability fixes                  | Operational debugging                                            | **GAP** — no `observability.py`. Chronicle is local-only today.                                 |
| Cron/watchers no-agent recipes                | Poll RSS / HTTP JSON / GitHub / scheduled probes                 | **PARTIAL** — `relic/gumi_plugin/cron_wiring.py` + `relic/checkin/scheduler.py`. Decision dataclass and `evaluate_no_agent_tick(envelope)` entrypoint missing. |
| Cross-session Claude prompt cache             | Lower latency for stable prompt sections                         | **GAP** — no `prompt_cache.py` classifier.                                                      |
| Per-turn verifier                             | Lightweight runtime guard                                        | Map onto existing `OutputCritic`; no separate verifier integration today.                       |
| Gateway and platform improvements             | More channels for Gumi interaction                               | `DeliveryGate` + allowlist store already enforce per-platform eligibility.                      |
| Local OpenAI-compatible proxy                 | Agentic development                                              | Out of scope for runtime governance.                                                            |

## Architecture (target, with mapping)

```text
Hermes gateways / CLI / API / cron / watchers
        |
        v
Relic adapter surface
  ├── envelope.py          (GAP)   → would normalize hook kwargs + HERMES_SESSION_ID + chat_id
  ├── identity.py          (GAP)   → sender_id → subject_ref mapping
  ├── hooks.py             (LIVE)  → hermes-plugin/tools/relic_shared_continuity/hooks.py
  ├── handoff_gate.py      (GAP)
  ├── cron_bridge.py       (PARTIAL) → relic/gumi_plugin/cron_wiring.py + relic/checkin/scheduler.py
  ├── observability.py     (GAP)
  ├── approvals.py         (GAP)
  ├── prompt_cache.py      (GAP)
  └── source_policy.py     (GAP — admission lives in gumi_continuity/admission + gumi_plugin/admission)
        |
        v
Relic governance core
        ├── identity, consent, source policy, admission policy, correction policy,
        ├── context pack builder (relic/context_pack/*)
        ├── output critic (relic/gumi_plugin/critic.py)
        └── delivery decision engine (relic/hermes_runtime.py DeliveryGate + RuntimeDecision)
        |
        v
Hermes execution surface (model / tool / handoff / delivery / approval stream)
        |
        v
Chronicle trace ledger (relic/chronicle/*) → SQLite + JSONL dual-write, redacted, append-only
  + Future redacted observability bridge → Hermes / Langfuse
```

The adapter must remain small. Relic core must not import arbitrary Hermes internals outside the adapter modules listed above.

## Module layout: target vs current

```text
relic/hermes_adapter/           # TARGET — not yet created
  __init__.py
  envelope.py                   # GAP
  identity.py                   # GAP
  hooks.py                      # GAP — current entrypoint lives in hermes-plugin/tools/relic_shared_continuity/hooks.py
  handoff_gate.py               # GAP
  cron_bridge.py                # GAP — current logic in relic/gumi_plugin/cron_wiring.py + relic/checkin/scheduler.py
  observability.py              # GAP
  approvals.py                  # GAP
  prompt_cache.py               # GAP
  source_policy.py              # GAP
  errors.py                     # GAP

relic/hermes_runtime.py         # LIVE — 715 LoC, session key + delivery gate + runtime decision enum
relic/hermes_plugin/            # LIVE — context injection, fail safe, tool permissions, plugin lifecycle
relic/gumi_plugin/cron_wiring.py # LIVE — no-agent cron decision
relic/checkin/                  # LIVE — check-in scheduler, question engine, facet updater
relic/chronicle/                # LIVE — Chronicle trace ledger (replaces planned relic/trace/)
hermes-plugin/tools/relic_shared_continuity/hooks.py  # LIVE — Hermes entrypoint
```

If the **rebrand path** is chosen, the adapter modules become aliases pointing to existing files. If the **façade path** is chosen, new modules wrap existing code without rewriting it. The contracts below are identical either way.

### `envelope.py` (GAP)

Builds `HermesRuntimeEnvelope` from Hermes metadata. See `docs/03-contracts-and-schemas.md` for fields. None of the current entrypoints construct an envelope; `pre_llm_call` consumes raw kwargs.

### `identity.py` (GAP)

Maps Hermes IDs to Relic IDs. Today `hooks.py` does `subject_id = sender_id or session_id` with no mapping policy or hashing. Identity work must:

- never assume `sender_id == subject_id`
- store platform-scoped IDs as hashed references
- keep user, subject, Gumi instance, Hermes profile, platform thread, and session distinct
- gate multi-chat → single-subject mapping behind explicit consent

### `hooks.py` (LIVE → needs adapter wrap)

Current behaviour in `hermes-plugin/tools/relic_shared_continuity/hooks.py`:

- `pre_llm_call` builds a `PromptContextPack` via `ContinuityAdmissionPolicy`, returns `None` or `{"context": str}`, fail-closed on exceptions. Runs `_run_safety_scan` in `finally`.
- `transform_llm_output` runs `OutputCritic` then falls back to a clinical-term filter, returning `None`, `"[SILENT]"`, or a replacement string.
- `post_llm_call` is a no-op.

Required upgrades:

- emit Chronicle events on context pack request, admitted items, blocked items, output review, output block
- read `chat_id` from `hook_ctx`
- consume an `HermesRuntimeEnvelope` instead of raw kwargs
- preserve every existing acceptance test in `tests/hermes_compat/`

### `handoff_gate.py` (GAP)

Authorizes `/handoff`. Record source session, target runtime mode, reason, actor type, profile snapshot, policy snapshot, context preservation choice, and risk-boundary crossing. Forbidden defaults unchanged from the original proposal.

### `cron_bridge.py` (PARTIAL)

Move current `cron_wiring.py` decision logic behind a stable bridge. Hermes owns scheduling; Relic returns `RuntimeDecisionResult`. Today `RuntimeDecision` exists as an **enum** in `relic/hermes_runtime.py`; the dataclass with `reason_codes`, `subject_ref`, `candidate_message`, `media_type`, `trace_event_id` is missing. `relic/checkin/scheduler.py` is a sibling scheduler — clarify ownership before adding the bridge.

### `observability.py` (GAP)

Bridges Chronicle events to Langfuse / external observability. Rules unchanged: external spans carry IDs, hashes, durations, decision codes, redaction markers — never raw subject text. Chronicle remains the audit source of record.

### `approvals.py` (GAP)

Normalizes Hermes approval events into Chronicle events. Each approval event records requested action, requesting tool / agent, target subject / profile scope, status, approver role, timestamp, redacted action summary, policy snapshot.

### `prompt_cache.py` (GAP)

Defines what may and may not be cached. Cache classes: `STATIC_SAFE`, `POLICY_VERSIONED`, `PROFILE_VERSIONED`, `NEVER_CACHE`. Invalidation keys: `profile_snapshot_id`, `policy_snapshot_id`, `correction_revision`, `context_pack_hash`, `admission_policy_version`, `output_critic_version`, `subject_status`.

### `source_policy.py` (GAP)

Classifies every incoming source before evidence promotion. Source classes and eligibility table in `docs/03-contracts-and-schemas.md`. Today admission logic is split between `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py`; the unified source-class taxonomy is not enforced at the runtime boundary.

## Trace architecture: Chronicle layer (LIVE)

The Relic-native append-only trace ledger landed as **Chronicle**, not as `relic/trace/`. Differences from the original proposal:

- **Dual write**: JSONL append (forensic journal at `~/.relic/chronicle/journal/{YYYY-MM-DD}.jsonl`) followed by SQLite insert (`chronicle_events` etc. via migrations `0003`–`0007`). The proposal called only for JSONL.
- **Five record kinds**: `Event`, `Decision`, `StateSnapshot`, `ProvenanceEdge`, `AccessLogEntry`. The proposal called for one (`RelicTraceEvent`).
- **Path**: `~/.relic/chronicle/journal/{YYYY-MM-DD}.jsonl`, not `~/.relic/traces/{subject_id}/{YYYY-MM-DD}.jsonl`. Subject scoping is via `subject_id` column inside the row, not via directory partitioning.
- **Schema source of truth**: `relic/chronicle/schema.py::Event` (Pydantic). The JSON Schema in `schemas/relic_trace_event.schema.json` is **forward-target only** and must be regenerated from the Pydantic model before being used as an enforcement contract.
- **Redaction**: built-in via `relic/chronicle/redaction.py` and `consent_gate.py`. Synthetic secret regression strings (see `docs/04-acceptance-tests.md`) are tested.
- **Retention reaper**: `relic/chronicle/retention.py` provides `delete_expired`, `archive_journal`, `run`.

Langfuse answers: what did the runtime do?
Chronicle answers: why was this profile/context/decision valid under policy?

### Event-type vocabulary

The plan listed a fixed event-type vocabulary (`runtime_received`, `identity_resolved`, `source_policy_checked`, `evidence_observed`, …). Chronicle does not enforce that exact list — `Event.event_type` is a free snake_case string validated only by regex, plus an `EventCategory` enum. Adapter modules must therefore standardise the event-type strings they emit so traces remain queryable. Recommended canonical set (subset to standardise first):

```text
runtime_received
identity_resolved
source_policy_checked
context_pack_requested
context_item_admitted
context_item_blocked
context_pack_rendered
llm_call_prepared
llm_output_reviewed
output_blocked
output_silenced
output_rewritten
output_passed
correction_applied
profile_snapshot_created
handoff_requested
handoff_allowed
handoff_blocked
delivery_decision_made
approval_requested
approval_resolved
observability_exported
```

Each event must include the Chronicle-mandatory fields (`event_id`, `trace_id`, `event_type`, `event_category`, `source_module`, `timestamp`, `sensitivity`, `visibility`, `retention_policy`, `schema_version`) plus, where applicable, `subject_id`, `hermes_profile_id`, `parent_event_id`, `payload_hash`, `payload` (redacted), `tags`.

## Integration pattern (unchanged in shape; mapped to current modules)

### Pre-LLM

```text
Hermes hook_ctx
  → HermesRuntimeEnvelope                                    (TARGET: relic/hermes_adapter/envelope.py)
  → identity mapping                                          (TARGET: relic/hermes_adapter/identity.py)
  → source policy                                             (TARGET: relic/hermes_adapter/source_policy.py)
  → continuity / admission policy                             (LIVE:   relic/gumi_continuity/admission.py)
  → context pack                                              (LIVE:   relic/context_pack/*)
  → redacted context injection                                (LIVE:   relic/hermes_plugin/context_injection.py)
  → Chronicle events                                          (LIVE:   relic/chronicle/emitter.py)
```

### Post-LLM

```text
LLM output
  → OutputCritic                                              (LIVE:   relic/gumi_plugin/critic.py)
  → forbidden claim filters                                   (LIVE:   hermes-plugin/tools/relic_shared_continuity/hooks.py FORBIDDEN_OUTPUT_TERMS)
  → replacement / pass-through / [SILENT]
  → Chronicle event
  → optional redacted observability span                      (TARGET: relic/hermes_adapter/observability.py)
```

### No-agent delivery

```text
Hermes cron/watcher tick
  → Relic cron bridge                                         (TARGET: relic/hermes_adapter/cron_bridge.py)
    → delivery policy                                         (LIVE:   relic/hermes_runtime.py DeliveryGate)
    → quiet hours                                             (LIVE:   relic/gumi_plugin/cron_wiring.py)
    → platform allowlist                                      (LIVE:   relic/hermes_runtime.py)
    → due followup check                                      (LIVE:   relic/checkin/scheduler.py)
    → media policy                                            (LIVE:   relic/gumi_plugin/media_state.py)
  → decision event (Chronicle)
  → Hermes delivery only if DELIVER
```

### Handoff

```text
Handoff requested
  → Relic handoff gate                                        (TARGET: relic/hermes_adapter/handoff_gate.py)
    → policy snapshot
    → risk boundary check
    → context preservation decision
  → Chronicle event
  → Hermes handoff or block
```

## Compatibility requirements

Existing test suites must keep passing. Add new tests instead of weakening current ones.

Required guarantees (verified by current `tests/hermes_compat/test_plugin_context_injection.py`, `test_plugin_failure_no_injection.py`, `test_plugin_context_pack_ephemeral.py`):

- Empty or invalid session returns no injected context.
- Hooks never return an error dict to Hermes.
- Blocked items never appear in injected context.
- False physical experience claims are blocked or silenced.
- Dependency escalation and clinical labels are blocked or rewritten.

New guarantees (to be added by adapter work):

- Cron decisions emit Chronicle events even when no delivery happens.
- Handoff cannot bypass OutputCritic.
- Langfuse export cannot contain raw subject text.
- Approval events carry policy snapshot reference.
- Prompt cache rejects profile-bearing sections without full invalidation keys.

## Migration strategy (revised)

Steps already completed (with deltas from original plan):

- **Step 1 (Wrap existing plugin behaviour)** — *Skipped.* `hermes-plugin/tools/relic_shared_continuity/hooks.py` was not routed through an adapter package; it still imports `relic.*` directly. To complete: add `relic/hermes_adapter/hooks.py`, move body, leave a thin Hermes-loadable shim.
- **Step 2 (Envelope and trace schema)** — *Trace half done as Chronicle; envelope not done.* Chronicle dual-writes to `~/.relic/chronicle/journal/*.jsonl` + SQLite. JSON Schema for events lives only in this pack and must be regenerated from `relic/chronicle/schema.py` before being used to validate samples.
- **Step 3 (Bridge cron)** — *Not started.* `cron_wiring.py` is intact; no `evaluate_no_agent_tick(envelope)` wrapper exists.
- **Step 4 (Handoff guard)** — *Not started.*
- **Step 5 (Observability bridge)** — *Not started.*
- **Step 6 (Docs and contract tests)** — *Partly done.* `docs/guides/hermes-integration.md` exists; trace-ledger and adapter docs do not. `tests/chronicle/` and `tests/hermes/` provide deep coverage; adapter-targeted hermes_compat tests are missing.

Next-step ordering for remaining work is in `docs/02-agentic-development-plan.md`.

## Risks and controls (unchanged)

| Risk                                                       | Control                                                                                  |
|------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Hermes runtime metadata treated as subject evidence        | `source_policy.py` (GAP) requires explicit admission before evidence use                |
| Prompt cache serves stale profile state                    | `prompt_cache.py` (GAP) invalidation keys include profile/policy/correction/context hashes |
| Handoff bypasses Relic governance                          | `handoff_gate.py` (GAP) required before any target mode switch                          |
| Langfuse receives sensitive payloads                       | `observability.py` (GAP) redacted export only; tests fail on raw text leaks             |
| Cron/watchers send proactive messages without consent      | `DeliveryGate` + `cron_bridge.py` keep Relic as delivery authority                      |
| Platform IDs leak identity                                 | `identity.py` (GAP) hashes scoped IDs and keeps raw IDs out of public traces            |
| Gumi diegetic events update subject model                  | Event-stream separation enforced in source policy                                       |

## Recommended implementation order (updated)

1. `HermesRuntimeEnvelope` + `identity.py` (no current equivalent — net new).
2. Adapter `hooks.py` wrap that consumes the envelope and emits Chronicle events for context pack request / admitted / blocked / output review / output block. Keep `hermes-plugin/tools/relic_shared_continuity/hooks.py` as a thin shim.
3. `cron_bridge.py` with `RuntimeDecisionResult` dataclass + `evaluate_no_agent_tick(envelope) -> RuntimeDecisionResult`, wrapping `relic/gumi_plugin/cron_wiring.py` and reading `relic/checkin/scheduler.py` status.
4. `handoff_gate.py` with `HandoffDecision` dataclass.
5. `approvals.py` normalization → Chronicle.
6. `observability.py` Langfuse redaction bridge.
7. `prompt_cache.py` policy classifier.
8. `source_policy.py` unifying `relic/gumi_continuity/admission` + `relic/gumi_plugin/admission`.
9. Regenerate `schemas/relic_trace_event.schema.json` from Pydantic `Event` (or retire it in favour of the Pydantic source-of-truth).
10. Docs: `docs/architecture/trace-ledger.md` (Chronicle), `docs/guides/hermes-v2026-5-16-upgrade.md`, `docs/reference/hermes-adapter.md`.

## Non-goals (unchanged)

This proposal does not recommend:

- moving Relic governance into Hermes core
- storing raw private messages in Langfuse
- using X search or public web signals for automatic trait inference
- treating generated media or Gumi diegetic events as user evidence
- replacing Relic correction and provenance rules with Hermes observability
- adding a Chronicle UI before the trace schema is stable (the Pydantic schema is stable; the JSON Schema mirror is not yet generated)

## Source references

- Hermes Agent release: https://github.com/NousResearch/hermes-agent/releases/tag/v2026.5.16
- Relic repository: https://github.com/yuzushi-dev/Relic
- Relic README: https://github.com/yuzushi-dev/Relic/blob/master/README.md
- Relic Hermes hooks: https://github.com/yuzushi-dev/Relic/blob/master/hermes-plugin/tools/relic_shared_continuity/hooks.py
- Relic Hermes runtime: https://github.com/yuzushi-dev/Relic/blob/master/relic/hermes_runtime.py
- Relic Hermes plugin internals: https://github.com/yuzushi-dev/Relic/tree/master/relic/hermes_plugin
- Relic cron wiring: https://github.com/yuzushi-dev/Relic/blob/master/relic/gumi_plugin/cron_wiring.py
- Relic check-in scheduler: https://github.com/yuzushi-dev/Relic/blob/master/relic/checkin/scheduler.py
- Relic Chronicle ledger: https://github.com/yuzushi-dev/Relic/tree/master/relic/chronicle
- Relic Hermes compatibility tests: https://github.com/yuzushi-dev/Relic/tree/master/tests/hermes_compat
- Relic Hermes contract tests: https://github.com/yuzushi-dev/Relic/tree/master/tests/hermes
- Relic Chronicle tests: https://github.com/yuzushi-dev/Relic/tree/master/tests/chronicle
