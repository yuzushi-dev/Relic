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

## Versioning

Relic does not use semantic versioning in alpha. Breaking changes may occur on `main` without a major version bump. Pin to a specific commit if you need stability.

When 1.0.0 is tagged, the stable modules above will have a committed API with semver guarantees.
