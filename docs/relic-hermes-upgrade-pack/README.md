# Relic Hermes Upgrade Pack

Originally a green-field proposal for integrating Relic with Hermes Agent v2026.5.16. This revision **aligns the plan to the codebase as of 2026-05-16**. Most boundary concepts survived; the package names, file paths, and trace architecture diverged during implementation.

Hermes acts as the runtime surface: gateways, sessions, tool execution, plugin hosting, scheduling, approvals, handoff, and operational observability.

Relic remains the governance and longitudinal modeling layer: subject profiles, evidence admission, correction, policy gates, context packs, traceable decisions, and audit artifacts.

## Reality check (codebase audit 2026-05-16)

| Plan name                              | Actual location                                          | Status                                                                 |
|----------------------------------------|----------------------------------------------------------|------------------------------------------------------------------------|
| `relic/hermes_adapter/`                | **Not created.** Logic spread across `relic/hermes_runtime.py`, `relic/hermes_plugin/`, `relic/gumi_plugin/`, `hermes-plugin/tools/relic_shared_continuity/` | Adapter façade still missing                                          |
| `HermesRuntimeEnvelope`                | Not present                                              | Hooks consume raw kwargs directly                                      |
| `RelicTraceEvent` + JSONL sink         | **Superseded by `relic/chronicle/`** — dual-write SQLite + JSONL, schemas in `relic/chronicle/schema.py`, migrations `0003`–`0007` | Larger scope than planned (events + decisions + snapshots + provenance edges + access log + consent gate + retention reaper) |
| Hook migration into adapter            | `hermes-plugin/tools/relic_shared_continuity/hooks.py` still calls `relic.*` directly | Entrypoint stable, no adapter wrap                                     |
| `cron_bridge.py` + `RuntimeDecisionResult` dataclass | `relic/gumi_plugin/cron_wiring.py` + `relic/checkin/scheduler.py` + `RuntimeDecision` **enum** in `relic/hermes_runtime.py` (715 LoC) | Bridge function and structured result dataclass missing               |
| `handoff_gate.py` / `HandoffDecision`  | Not present                                              | Open                                                                   |
| `approvals.py`                         | Not present                                              | Open                                                                   |
| `observability.py` (Langfuse bridge)   | Not present                                              | Open                                                                   |
| `prompt_cache.py` policy               | Not present                                              | Open                                                                   |
| `source_policy.py`                     | Not present (admission lives in `relic/gumi_plugin/admission.py` + `relic/gumi_continuity/admission.py`) | Source-class taxonomy not enforced uniformly                          |
| Schemas `hermes_runtime_envelope.schema.json`, `relic_trace_event.schema.json` | Present in this pack only. Actual repo ships `schemas/hermes/*` (checkpoint, delivery_gate, no_agent_cron_mode, platform_allowlist, rollback_flag, session_key, transform_llm_output_hook) | Pack schemas remain forward-target                                    |
| Docs `architecture/trace-ledger.md`, `guides/hermes-v2026-5-16-upgrade.md`, `reference/hermes-adapter.md` | Not written. `docs/guides/hermes-integration.md` exists | Open                                                                   |
| Tests `tests/trace/*`, `tests/hermes_compat/test_runtime_envelope.py`, `test_handoff_gate.py`, `test_approval_events.py`, `test_observability_redaction.py`, `test_prompt_cache_policy.py` | Replaced by `tests/chronicle/*` (12 files) + `tests/hermes/*` (10 contract tests) + existing `tests/hermes_compat/*` (8 files). New adapter-targeted tests not added | Coverage exists for trace ledger and Hermes runtime contracts; envelope/handoff/approvals/observability/cache uncovered |

## Files

| File                                       | Purpose                                                                          |
|--------------------------------------------|----------------------------------------------------------------------------------|
| `docs/01-upgrade-proposal.md`              | Architectural proposal with mapping to current modules and remaining gaps.       |
| `docs/02-agentic-development-plan.md`      | Re-phased plan starting from current state (Phase 0–2 partly done).              |
| `docs/03-contracts-and-schemas.md`         | Contract specs reconciled with `relic.chronicle.schema` and `relic.hermes_runtime`. |
| `docs/04-acceptance-tests.md`              | Test matrix updated to actual `tests/chronicle`, `tests/hermes`, `tests/hermes_compat` layout. |
| `docs/ADR-001-hermes-runtime-boundary.md`  | ADR — Accepted in principle; trace ledger realized as Chronicle, adapter package still pending. |
| `schemas/relic_trace_event.schema.json`    | **Forward-target** schema. Source of truth today is `relic/chronicle/schema.py::Event`. |
| `schemas/hermes_runtime_envelope.schema.json` | **Forward-target** schema. No code implements it yet.                          |
| `agentic/ORCHESTRATOR_PROMPT.md`           | Orchestrator prompt updated to point at real files.                              |
| `agentic/WORKER_CONTRACT.md`               | General worker contract (mostly unchanged).                                      |
| `tasks/worker_task_packets.md`             | Task packets pruned (done removed) and reframed as forward-port from current state. |

## Scope

This pack is a proposal **and** a reconciliation. It now references the real public Relic repository state — including `relic/chronicle/`, `relic/checkin/`, `relic/hermes_runtime.py`, and the existing `hermes-plugin/` and `relic/hermes_plugin/` directories — rather than assuming a blank slate.

## Two viable paths forward

1. **Rebrand path** — accept that Chronicle = trace ledger, `relic/hermes_runtime.py` + `relic/hermes_plugin/` = de-facto adapter. Document divergences, retire the `hermes_adapter/` name, fill missing pieces (handoff gate, approvals, observability bridge, prompt cache policy) inside existing modules.
2. **Façade path** — create `relic/hermes_adapter/` as a thin façade over existing code, surfacing `HermesRuntimeEnvelope`, `RuntimeDecisionResult`, `HandoffDecision` dataclasses and re-exporting Chronicle emitters under adapter-flavored names.

The phased plan in `docs/02-agentic-development-plan.md` is written for the **façade path** because it keeps the boundary explicit and review-friendly. Switching to the rebrand path only changes file locations, not contracts.

## Target outcome (unchanged)

Stable adapter surface, audit-grade trace events (Chronicle), redacted observability, governed handoff, governed proactive delivery, source-policy enforcement, and a development plan agents can execute without re-deriving architecture.
