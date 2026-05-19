# Release Status

Relic is in alpha. This page documents which modules are stable enough to depend on, which are experimental, and which are internal.

## Status definitions

**Stable** — The public interface is unlikely to change without a deprecation notice. Tests cover the main contracts. Safe to build on.

**Experimental** — Under active development. The interface may change between alpha releases without notice. Use it, but expect breakage.

**Internal** — Not intended as a public interface. May be reorganized, renamed, or removed at any time.

## Module stability

| Module | Status | Notes |
|---|---|---|
| `relic/artifacts/` | Stable | Registry, checksums, type definitions |
| `relic/bootstrap/` | Stable | Bootstrap entry points |
| `relic/cac/` | Stable | Interface may gain fields; existing fields stable |
| `relic/cli.py` | Stable | Command names and flags are stable; new subcommands may be added |
| `relic/compiler/` | Stable | Pipeline is stable; individual passes may change |
| `relic/config.py` | Stable | Environment variable names are stable |
| `relic/context_pack/` | Stable | PromptContextPack schema is stable |
| `relic/control/` | Stable | Consent, delete, export, pause operations |
| `relic/correction/` | Stable | Propagation interface is stable |
| `relic/db/` | Stable | |
| `relic/eval/` | Experimental | Metrics and harness interface are evolving |
| `relic/gumi/` | Experimental | Background generation and personalization are evolving |
| `relic/gumi_continuity/` | Stable | Admission, event, recall, store interfaces |
| `relic/gumi_memory/` | Experimental | Provider interface stable; individual providers experimental |
| `relic/gumi_plugin/` | Experimental | Hook signatures stable; media and cron features evolving |
| `relic/gumi_roleplay/` | Stable | Admission interface stable |
| `relic/hermes_plugin/` | Stable | Hook signatures and tool interfaces stable |
| `relic/hermes_runtime.py` | Stable | Runtime defaults and session key management |
| `relic/lab/` | Experimental | Dataset contracts may tighten as data pipeline matures |
| `relic/memory_dynamics/` | Experimental | Algorithms under active research |
| `relic/patterns/` | Stable | Signal extractor and confidence caps interfaces stable |
| `relic/persistence.py` | Stable | |
| `relic/privacy/` | Stable | Gateway, PII, policy, trace interfaces stable |
| `relic/profile/` | Stable | Registry and bootstrap TUI stable; inferred fields evolving |
| `relic/replication/` | Stable | |
| `relic/safety/` | Stable | Escalation notifier interface stable |
| `relic/schemas.py` | Stable | Shared schema definitions |
| `relic/shared_continuity/` | Stable | Service and lifecycle interfaces stable |
| `relic/ui/` | Experimental | UI contracts stable; view models and workbench panels evolving |
| `relic/vault/` | Stable | Export and import interfaces stable |

## Known gaps in alpha

- No stable Python API for external integrations. Everything above is stable at the CLI and internal interface level; a proper public API with versioning is planned post-alpha.
- SQLite only. PostgreSQL migration is defined but not yet automated.
- Memory provider coverage is uneven. Hindsight local mode is the most tested; Byterover, Holographic, and Honcho are experimental.
- End-to-end Hermes integration tests require a live Hermes installation and are not part of the standard test suite.
- The researcher UI (`relic ui`) is a prototype. The contracts it must meet are tested; the actual UI rendering is not.

## Feature status at a glance

A flatter view oriented at researchers deciding what to depend on. Status legend below.

| Feature | Status | Notes |
|---|---|---|
| Bootstrap TUI (`relic subject create`) | Stable | Mixed IT/EN prompts; resumable |
| Subject lifecycle (create/show/reprovision/forget) | Stable | GDPR-aligned forget; pause is session-level only via `/relic pause` |
| Researcher workbench panels | Beta | 12 panels; contracts tested, render layer is a prototype |
| Workbench corrections + recompile | Stable | Authoritative, propagates |
| Workbench export/delete buttons | Gated | `EXPORT_BUNDLE` permission not granted by default |
| CAC scoring + traces | Stable | Deterministic rules, immutable traces |
| Shared Continuity memory | Stable | Subject-confirmed markers, recall limits |
| Memory provider: Hindsight (local) | Stable | Default for full Gumi |
| Memory provider: builtin / holographic | Stable | Local, lower-power options |
| Memory provider: Byterover / Honcho | Eval fixtures only | Live providers not enabled as runtime defaults |
| Telegram delivery | Stable | Per-subject bot, allowlist, quiet hours, frequency cap |
| WhatsApp delivery | Not implemented | Allowlist accepts the string; no adapter |
| Email / SMS delivery | Not implemented | Same |
| Gemini media (images, TTS, music) | Beta | Requires `GEMINI_API_KEY`; quota-bound |
| Chronicle ledger + queries | Stable | Default retention 365 days; reaper opt-in |
| `chronicle delete` / GDPR forget | Stable | Always preview with `--dry-run` |
| `chronicle reaper` | Stable | Manual or scheduled |
| Provenance edges (PROV-O) | Stable | `chronicle provenance` |
| Safety signals (tiers, categories) | Stable | Researcher-facing only |
| Evaluation harness (`scripts/eval_run.py`) | Beta | Metrics evolving; mock model deterministic |
| Demo data generator + e2e bundle | Stable | `scripts/generate_demo_data.py`, `scripts/demo_e2e.py` |
| Replication bundles | Stable | Produced by compiler and eval |
| SQLite backend | Stable | Default |
| PostgreSQL backend | Migration-only | SQL provided, runtime adapter not shipped |
| Multi-researcher with IdP | Out of scope | OSS distribution has no auth; wrap in IdP |
| Schema auto-migration | Stable | Applied at startup |
| Cron-scheduled proactivity | Stable | Subject-scoped; consent + pause gated |
| `/relic why`, `/relic pause`, `/relic resume`, `/relic status` | Stable | In-session, researcher-only |

**Status legend:** *Stable* — depend on it. *Beta* — usable, expect breakage between releases. *Eval fixtures only* — exists for evaluation, not for production routing. *Not implemented* — the string is accepted somewhere, but no code path delivers. *Out of scope* — by design, not on the public roadmap. *Migration-only* — assets ship, runtime wiring requires engineering work.

## What is on the near roadmap

These are likely between alpha and 1.0; not a commitment:

- A public Python API surface for external integrations (currently CLI-only).
- A runtime adapter for PostgreSQL behind a single config switch.
- A first-class research API for ad-hoc queries beyond `chronicle`.
- Hardening of the workbench render layer (currently the contract is tested, the pixels are not).

## What is NOT on the roadmap

- WhatsApp / Email / SMS adapters.
- Built-in auth, password storage, MFA. Use an IdP.
- A SaaS deployment. Relic is a researcher-on-a-machine tool by design.
- Clinical scales, scoring, or anything that would make the system a clinical instrument.

## Versioning

Relic does not use semantic versioning in alpha. Breaking changes may occur on `main` without a major version bump. Pin to a specific commit if you need stability.

When 1.0.0 is tagged, the stable modules above will have a committed API with semver guarantees.
