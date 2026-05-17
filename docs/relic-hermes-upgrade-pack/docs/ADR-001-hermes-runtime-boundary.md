# ADR-001: Keep Hermes as Runtime and Relic as Governance Layer

## Status

**Accepted in principle.** Boundary decision is upheld by current codebase. Adapter package (`relic/hermes_adapter/`) named in this ADR is **not yet implemented** — the adapter surface is currently distributed across `relic/hermes_runtime.py`, `relic/hermes_plugin/`, `relic/gumi_plugin/cron_wiring.py`, `relic/checkin/`, and the upstream `hermes-plugin/tools/relic_shared_continuity/` entrypoint. The trace ledger half of this decision landed as **Chronicle** (`relic/chronicle/`) rather than as a thin `relic/trace/` JSONL sink (see Consequences → Deviations).

## Context

Hermes Agent v2026.5.16 adds or improves runtime features that overlap with parts of Relic's integration surface: handoff, plugin LLM calls, session metadata, cron/watchers, approval events, observability, prompt caching, platform gateways, and local OpenAI-compatible proxy support.

Relic already contains Hermes hooks (`hermes-plugin/tools/relic_shared_continuity/hooks.py`), output criticism (`relic/gumi_plugin/critic.py`), context injection (`relic/hermes_plugin/context_injection.py`), cron decision logic (`relic/gumi_plugin/cron_wiring.py`), session-key handling and delivery gate (`relic/hermes_runtime.py`), and a strong data separation model for subject evidence, Gumi diegetic events, generated media, and runtime context.

Without a clear boundary, the integration can drift into duplicate scheduling, hidden profiling, stale prompt state, or unclear audit provenance.

## Decision

Relic integrates with Hermes through a dedicated adapter layer (target: `relic/hermes_adapter/`; current: distributed across the modules listed above).

Hermes owns:

- gateway transport
- session execution
- tool execution
- plugin hosting
- scheduling and watcher ticks
- handoff mechanics
- approval stream transport
- operational observability

Relic owns:

- identity mapping
- subject and Gumi profile separation
- source policy
- evidence admission
- context pack creation
- correction state
- output critic
- proactive delivery decisions
- handoff authorization
- audit-grade trace ledger (Chronicle)
- audit-grade provenance

## Consequences

### Benefits

- Relic can use Hermes features without inheriting Hermes internals everywhere.
- Governance stays testable and inspectable (verified by `tests/hermes_compat/`, `tests/hermes/`, `tests/hermes_plugin/`).
- Delivery and handoff cannot bypass Relic policy gates.
- Langfuse and Hermes observability can be useful without becoming the source of audit truth.
- Agentic development tasks become smaller and safer.

### Costs

- A new adapter package must be maintained.
- Hermes release changes may require adapter updates.
- There is some duplication in metadata models; this is intentional boundary protection.

### Deviations from the originally proposed implementation (recorded 2026-05-16)

- **Trace ledger**: implemented as Chronicle (`relic/chronicle/`) with dual-write JSONL + SQLite, five record types (`Event`, `Decision`, `StateSnapshot`, `ProvenanceEdge`, `AccessLogEntry`), migrations `0003`–`0007`, redaction, consent gate, retention reaper, access audit. The proposal called for a thin `relic/trace/` JSONL sink with a single `RelicTraceEvent` type — Chronicle is a larger superset.
- **Adapter package**: not created. The functions that would have lived in `relic/hermes_adapter/{envelope,identity,hooks,handoff_gate,cron_bridge,observability,approvals,prompt_cache,source_policy,errors}.py` are absent (envelope, identity, handoff_gate, observability, approvals, prompt_cache, source_policy) or distributed across other modules (hooks, cron_bridge equivalent logic). This decision remains binding; the implementation has simply not happened yet.
- **Cron decision result**: `RuntimeDecision` is an Enum in `relic/hermes_runtime.py`, not the prescribed dataclass `RuntimeDecisionResult`. Dataclass with `reason_codes`, `subject_ref`, `candidate_message`, `media_type`, `trace_event_id` still to be written.
- **Hook migration**: the upstream entrypoint `hermes-plugin/tools/relic_shared_continuity/hooks.py` still imports `relic.*` directly without an adapter wrap.

These deviations do not invalidate the decision. They are tracked in `docs/02-agentic-development-plan.md`.

## Alternatives rejected

### Move Relic logic into Hermes plugin scripts only

Rejected because it spreads governance into plugin glue code and makes testing harder.

### Let Hermes cron/watchers directly send proactive Gumi messages

Rejected because proactive delivery requires Relic policy, quiet hours, opt-out, source, and consent checks. Currently enforced by `DeliveryGate` + `cron_wiring.py`.

### Use Langfuse as the main Relic audit ledger

Rejected because external observability is not the same as audit-grade provenance. Chronicle is the audit source of record; Langfuse remains an operational debugging surface.

### Cache whole prompts across sessions

Rejected because profile, correction, and policy state can change. Only stable or versioned prompt sections may be cached. `prompt_cache.py` classifier still to be written.
