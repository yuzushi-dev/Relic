# Module Map

This table covers the main packages in `relic/`. For detailed documentation on any package, follow the links to the relevant architecture or concept pages.

| Package | Responsibility | Stability |
|---|---|---|
| `relic/artifacts/` | Artifact registry, checksums, type definitions | Stable |
| `relic/bootstrap/` | Bootstrap entry points | Stable |
| `relic/cac/` | Context-Aware Controller: scores and filters hint candidates per turn | Stable |
| `relic/cli.py` | CLI entry point (`relic` command) | Stable |
| `relic/compiler/` | Profile compilation pipeline: passes, lineage, replication bundles | Stable |
| `relic/config.py` | Runtime configuration from environment and defaults | Stable |
| `relic/context.py` | Request context utilities | Stable |
| `relic/context_pack/` | PromptContextPack builder and adapters | Stable |
| `relic/control/` | Subject control operations: consent, delete, export, pause, incident | Stable |
| `relic/correction/` | Correction propagation from feedback event to stale artifacts | Stable |
| `relic/db/` | Database connection and loader | Stable |
| `relic/eval/` | Evaluation harness, metrics, ablation, fixture utilities | Experimental |
| `relic/gumi/` | Gumi background generation, initial contact, personalization | Experimental |
| `relic/gumi_continuity/` | Admission, event recording, recall, storage for Gumi continuity | Stable |
| `relic/gumi_memory/` | External memory provider interface and built-in providers | Experimental |
| `relic/gumi_plugin/` | Hermes plugin hooks, tools, cron, TTS, image generation, media dispatch | Experimental |
| `relic/gumi_roleplay/` | Roleplay admission controller | Stable |
| `relic/hermes_plugin/` | Hermes plugin: context injection, soul loader, tool permissions, fail-safe | Stable |
| `relic/hermes_runtime.py` | Hermes runtime defaults, session key management, delivery gate | Stable |
| `relic/lab/` | Dataset card, training/eval contracts, promote and validate for lab use | Experimental |
| `relic/memory_dynamics/` | Decay, reinforcement, association, consolidation, projection | Experimental |
| `relic/paths.py` | Path resolution utilities | Stable |
| `relic/patterns/` | Confidence caps, policy compiler, signal extractor, sanitizer | Stable |
| `relic/persistence.py` | Persistence utilities | Stable |
| `relic/privacy/` | Privacy gateway, PII detection, inference controls, policy, traces | Stable |
| `relic/privacy_gate.py` | Privacy gate entry point | Stable |
| `relic/profile/` | Profile registry, bootstrap TUI, inferred fields, system inference, projection | Stable |
| `relic/profiles.py` | Profile access utilities | Stable |
| `relic/replication/` | Replication bundle assembly | Stable |
| `relic/safety/` | Escalation notifier for safety signals | Stable |
| `relic/schemas.py` | Shared schema definitions | Stable |
| `relic/shared_continuity/` | Shared continuity memory: follow-up lifecycle, service | Stable |
| `relic/snapshot.py` | Snapshot utilities | Stable |
| `relic/ui/` | Researcher UI: API, audit, contracts, feedback, permissions, replay, workbench panels | Experimental |
| `relic/vault/` | Export and import of subject data bundles | Stable |

## External packages

| Package | Location | Responsibility |
|---|---|---|
| Hermes plugin (standalone) | `hermes-plugin/` | Standalone shared continuity plugin for Hermes |
| Hermes plugin (installed) | `hermes_plugin/` | Installed variant |

## Stability definitions

**Stable**: the public interface is unlikely to change without a deprecation period. Tests cover the core contracts.

**Experimental**: under active development. The interface may change. Use it, but expect breakage between alpha releases.

**Internal**: not part of the public interface. May be reorganized or removed without notice.
