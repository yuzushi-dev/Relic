# Paper-to-Codebase Map

This document connects the Relic/Gumi research paper to the current implementation. It is written for readers who need both views at once: the academic argument behind the system and the concrete code paths that realize, test, or limit that argument.

The canonical paper framing is `relic_gumi_paper_package/manuscript/relic-gumi-manuscript.md`. The canonical public implementation status is [Release Status](../contributing/release-status.md). The current codebase is the authority for all implementation claims.

## One-sentence project description

Relic is a governance and longitudinal modeling layer for subject-specific, diegetic relational agents; Gumi is the participant-facing companion agent governed by Relic; Hermes is the runtime surface through which Gumi runs, receives context, uses tools, schedules proactive checks, and delivers messages.

The paper's central claim is that relational memory should be inspectable, correctable, bounded, and non-clinical. The codebase implements that claim through scoped data models, subject-confirmed continuity markers, researcher-facing safety signals, runtime gates, Chronicle audit events, and contract tests.

## Academic contribution and implementation surface

| Paper contribution | Academic claim | Main implementation references | Verification references |
|---|---|---|---|
| Governance architecture for diegetic relational agents | Relic separates subject foundations, runtime mediation, safety governance, relational memory, and researcher oversight. | `relic/profile/`, `relic/hermes_runtime.py`, `relic/hermes_adapter/`, `relic/context_pack/`, `relic/ui/`, `relic/chronicle/` | `tests/profile/`, `tests/hermes/`, `tests/hermes_compat/`, `tests/ui/`, `tests/chronicle/` |
| Shared Continuity Memory | Gumi may remember only subject-confirmed relational markers, preserving subject words, corrections, follow-up permissions, TTL, and recall limits. | `relic/shared_continuity/service.py`, `relic/gumi_continuity/`, `relic/context_pack/adapters/continuity.py` | `tests/shared-continuity/`, `tests/gumi_continuity/`, `tests/ui/test_shared_continuity_panel_contract.py` |
| Safety governance without clinicalization | Safety signals are researcher-facing governance objects, not memories, diagnoses, or Gumi-facing labels. | `relic/patterns/signal_extractor.py`, `relic/patterns/policy_compiler.py`, `relic/patterns/runtime_pack_sanitizer.py`, `relic/safety/`, `relic/ui/workbench_panels.py` | `tests/safety/`, `tests/gumi_continuity/test_sensitive_signal_not_stored_as_continuity_marker.py`, `tests/ui/test_safety_signals_panel_contract.py` |
| Runtime mediation | Delivery, session identity, proactivity, output transformation, platform allowlists, and resume behavior are governed rather than implicit. | `relic/hermes_runtime.py`, `relic/hermes_adapter/`, `relic/hermes_plugin/`, `relic/gumi_plugin/cron_wiring.py`, `hermes-plugin/tools/relic_shared_continuity/hooks.py` | `tests/hermes/`, `tests/hermes_compat/`, `tests/hermes_plugin/`, `tests/gumi_plugin/` |
| Researcher oversight | Researchers inspect separated panels for safety, continuity, behavior constraints, delivery, session state, evaluation, audit, and export/delete/forget. | `relic/ui/api.py`, `relic/ui/workbench_panels.py`, `relic/ui/contracts.py`, `relic/ui/view_models.py`, `fixtures/researcher-workbench/` | `tests/ui/` |
| Evaluation framework | The system is evaluated for identity stability, boundary integrity, non-clinical language, backend non-disclosure, anti-dependency behavior, and anti-tracker collapse. | `relic/eval/`, `relic/lab/`, `fixtures/gumi-eval/`, `fixtures/memory-positive/`, `fixtures/gumi-roleplay/` | `tests/eval/`, `tests/gumi-eval/`, `tests/gumi_roleplay/`, `tests/lab/` |

## Paper structure mapped to code

### 1. Introduction: memory as a governance problem

The paper begins from a risk: persistent relational agents become valuable because they remember, but the same memory can become surveillance, clinical overreach, manipulation, or opacity.

The codebase encodes this problem as separation of data streams:

- subject scope is represented in `relic/profile/registry.py`, `relic/hermes_runtime.py`, and the data model documented in [Data Model](../architecture/data-model.md)
- Gumi-facing memory is separated from researcher-facing safety signals in `relic/shared_continuity/`, `relic/gumi_continuity/`, `relic/patterns/`, and `relic/safety/`
- auditability is handled by Chronicle in `relic/chronicle/`
- runtime context is assembled through `relic/context_pack/`, not by treating the database as a prompt

The implementation test strategy mirrors the introduction's concern: contract tests assert no cross-subject leakage, no raw clinical labels in continuity markers, no blocked context injection, and no delivery without gates.

### 2. Background: scrutable models, relational agents, memory, and self-tracking

The paper situates Relic in scrutable user modeling, relational agents, long-term LLM memory, personal informatics, JITAI-style decision points, and clinical decision support boundaries.

The codebase does not implement psychometrics as clinical measurement. Instead, it implements governed representation:

- bootstrap and profile collection live in `relic/bootstrap/` and `relic/profile/`
- context admission lives in `relic/context_pack/`, `relic/gumi_plugin/admission.py`, and `relic/gumi_continuity/admission.py`
- safety signal extraction explicitly forbids diagnosis labels in `relic/patterns/signal_extractor.py`
- evaluation fixtures test collapse modes such as clinical assistant collapse, mood tracker collapse, backend disclosure, and identity collapse in `fixtures/gumi-eval/`

The important research-to-code translation is this: the system does not ask "what condition does this subject have?" It asks "what representation is allowed to affect Gumi's behavior, under which visibility and recall constraints?"

### 3. Design problem: five tensions

| Paper tension | Code-level boundary |
|---|---|
| Memory versus surveillance | `ContinuityService` requires subject confirmation and enforces recall eligibility, TTL, recall count, and forget/pause operations. |
| Safety versus relational identity | `OutputCritic`, runtime pack sanitizer, and behavior policy compilation constrain language without exposing researcher-only labels to Gumi. |
| Continuity versus tracking | Shared Continuity stores descriptive subject words; tests reject clinicalized or tracker-like representations. |
| Diegesis versus transparency | Gumi-facing runtime context avoids backend machinery, while consent, workbench, Chronicle, export, and delete surfaces make the study inspectable. |
| Proactivity versus burden | `DeliveryGate`, cron wiring, quiet hours, allowlists, pause state, and `RuntimeDecision` values make "no reply" a governed outcome. |

These tensions are not comments in the code; they are expressed as invariants. For example, `tests/shared-continuity/test_continuity_clinicalization_guard.py` protects continuity from clinical labels, while `tests/gumi_plugin/test_cron_pause_controller_gate.py` and related cron tests protect proactive delivery from becoming unconditional outreach.

## System architecture by layer

### Layer 1: Study, subject, and consent foundation

The paper says every Gumi instance belongs to a study, condition, and subject, and that consent scopes gate delivery, proactivity, shared continuity, media, researcher review, export, and deletion.

Implementation references:

- `relic/profile/registry.py` defines `SubjectProfile`, profile registry operations, subject creation, Hermes provisioning, delivery configuration, and consent-mediated media flags.
- `relic/profile/bootstrap_tui.py` collects profile, consent, delivery, Gumi review, and Hermes provisioning inputs through a guided TUI.
- `relic/profile/_bootstrap_steps/consent.py` collects explicit consent with no assumed defaults.
- `relic/bootstrap/__init__.py` builds normalized bootstrap outputs and enforces conservative defaults.

Tests:

- `tests/profile/test_bootstrap_tui_flow.py`
- `tests/profile/test_gumi_hermes_cli.py`
- `tests/profile/test_hermes_plugin_provisioning.py`
- `tests/bootstrap/`

Status: implemented for the alpha workflow, with mixed Italian/English prompts and evolving inferred fields.

### Layer 2: Bootstrap and Gumi profile provisioning

The paper frames Gumi as subject-specific but not a copy of the subject. The bootstrap seeks calibrated relational distance: enough resonance for continuity, enough difference to preserve Gumi's agency and boundaries.

Implementation references:

- `relic/bootstrap/__init__.py` generates PR28 bootstrap outputs, sweet-spot report data, first-contact material, and consent-aware media configuration.
- `relic/profile/bootstrap_tui.py` orchestrates interactive collection, review, Hermes provisioning, media canon provisioning, and optional first-contact delivery.
- `relic/profile/registry.py` writes subject homes, Gumi seed artifacts, Hermes profile artifacts, delivery policy, media policy, and runtime files.
- `schemas/bootstrap/` and `schemas/profile/` validate generated artifacts.

The implementation does not treat bootstrap answers as permission to bypass hard safety defaults. Project-level guardrails remain conservative even when a subject expresses permissive preferences.

### Layer 3: Canonical data, artifacts, and audit

The paper says runtime context is not the database and vector/memory providers are not authoritative.

Implementation references:

- `relic/db/` and `relic/persistence.py` provide local SQLite persistence primitives.
- `relic/artifacts/` handles artifact registry, checksums, and type definitions.
- `relic/compiler/` produces profile artifacts and replication bundles.
- `relic/chronicle/` records events, decisions, snapshots, provenance edges, access audit, retention, and redaction.
- `relic/replication/` and `replication/` package reproducible bundles.

Chronicle is the audit spine. It answers "what happened and why?" rather than "what does the system currently believe?" That distinction is documented in [Chronicle](../architecture/chronicle.md).

### Layer 4: Hermes runtime mediation

The paper positions Hermes as runtime and Relic as governance.

Implementation references:

- `relic/hermes_runtime.py` defines session key hashing, delivery gate decisions, platform allowlist enforcement, runtime decision enums, Hermes profile rendering, feature checks, and resume reconciliation helpers.
- `relic/hermes_adapter/` defines a boundary facade for runtime envelopes, identity mapping, Chronicle helper emission, cron bridge, handoff gate, approvals, redacted observability, prompt cache policy, and source policy.
- `relic/hermes_plugin/` provides installed plugin commands, hooks, context injection, fail-safe behavior, resume hooks, memory provider wiring, and tool permission checks.
- `hermes-plugin/tools/relic_shared_continuity/hooks.py` is the standalone Hermes-loadable shared-continuity hook.

Important current limitation: the adapter facade exists and has contract tests, but not every live Hermes path delegates through it yet. The standalone hook still has compatibility fallback behavior. Treat `relic/hermes_adapter/` as the implemented boundary contract and the older live paths as compatibility surfaces still being migrated.

Tests:

- `tests/hermes/`
- `tests/hermes_compat/`
- `tests/hermes_plugin/`
- `tests/gumi_plugin/`

### Layer 5: Sensitive pattern governance

The paper distinguishes sensitive pattern candidates from memories and diagnoses.

Implementation references:

- `relic/patterns/signal_extractor.py` maps event streams to allowed non-diagnostic signal families and governance categories.
- `relic/patterns/policy_compiler.py` compiles safety patterns into label-stripped behavior constraints.
- `relic/patterns/runtime_pack_sanitizer.py` blocks forbidden clinical terms from reaching Gumi runtime packs.
- `relic/safety/signal_aggregator.py` aggregates repeated non-crisis signals.
- `relic/safety/escalation_notifier.py` handles escalation notification.
- `relic/safety/signal_audit.py` records redacted safety signal audit entries.

Tests:

- `tests/safety/`
- `tests/gumi_continuity/test_sensitive_signal_not_stored_as_continuity_marker.py`
- `tests/ui/test_safety_signals_panel_contract.py`

The implementation supports the paper's claim that safety governance can adjust behavior without telling Gumi or the subject that a hidden clinical label exists.

### Layer 6: Shared Continuity Memory

The paper's memory contribution is Shared Continuity Memory: subject-confirmed relational memory, not broad retrieval.

Implementation references:

- `relic/shared_continuity/service.py` implements markers, follow-ups, corrections, recall eligibility, TTL, recall count, forget, pause, resume, and clinicalization guards.
- `relic/shared_continuity/followup_lifecycle.py` implements follow-up lifecycle behavior.
- `relic/gumi_continuity/store.py` wraps the shared service for Gumi continuity usage.
- `relic/gumi_continuity/admission.py` decides which continuity candidates may enter runtime context.
- `relic/context_pack/adapters/continuity.py` converts admitted continuity markers into prompt-context items.

Tests:

- `tests/shared-continuity/`
- `tests/gumi_continuity/`
- `tests/ui/test_shared_continuity_panel_contract.py`

Status nuance: the service interface is stable. The service defaults to in-process, but an optional SQLite-backed repository (`relic/shared_continuity/repository.py` + migration `0013_shared_continuity.sql`) now persists confirmed markers, authoritative corrections, scope state, and marker lifecycle events across process restart, with a tested backup/restore drill (`relic/eval/shared_continuity_recovery.py`). Durable persistence is therefore implemented as an injectable artifact, not only target architecture; what remains unproven is multi-week field durability under live deployment.

### Layer 7: Researcher workbench and evaluation

The paper describes a researcher workbench that separates Safety Signals, Behavior Constraints, Shared Continuity, Delivery, Session/Resume, Evaluation, Audit, and Export/Delete/Forget.

Implementation references:

- `relic/ui/workbench_panels.py` defines panel classes and hard panel boundaries.
- `relic/ui/contracts.py` defines visible claim lineage, feedback, review queues, and exception-workbench defaults.
- `relic/ui/view_models.py` defines redacted-by-default view models.
- `relic/ui/api.py` exposes fixture-backed read-only study overview and subject registry handlers.
- `fixtures/researcher-workbench/` and `fixtures/ui/` provide contract fixtures.

Tests:

- `tests/ui/test_workbench_panel_separation.py`
- `tests/ui/test_safety_signals_panel_contract.py`
- `tests/ui/test_shared_continuity_panel_contract.py`
- `tests/ui/test_study_dashboard_contract.py`
- `tests/ui/test_workbench_permissions_contract.py`

Status nuance: the workbench contracts and fixtures are substantial, but the Python backend is fixture-backed/read-only for several surfaces. Do not present it as a complete live operational backend for every panel.

## Runtime flow: from participant turn to governed response

1. **Subject and session scope are established.**  
   `relic/hermes_runtime.py` derives session key hashes and delivery gate state. `relic/hermes_adapter/envelope.py` and `identity.py` define the intended normalized boundary for runtime metadata.

2. **Context candidates are assembled.**  
   `relic/context_pack/` builds a `PromptContextPack`. Continuity candidates come through `relic/shared_continuity/` and `relic/context_pack/adapters/continuity.py`.

3. **Admission decides what Gumi may receive.**  
   `relic/gumi_continuity/admission.py` and `relic/gumi_plugin/admission.py` keep blocked or unsafe items out of runtime context.

4. **Gumi output is reviewed.**  
   `relic/gumi_plugin/critic.py` and the standalone Hermes hook's fallback term filter block or rewrite false lived experience, dependency/need claims, clinical labels, and backend disclosure patterns.

5. **Delivery is gated.**  
   `DeliveryGate` in `relic/hermes_runtime.py`, cron wiring in `relic/gumi_plugin/cron_wiring.py`, and check-in policy in `relic/checkin/` enforce allowlists, consent, pause state, quiet hours, cadence, and no-agent decisions.

6. **Audit and provenance are recorded.**  
   `relic/chronicle/` stores structured events, decisions, snapshots, provenance edges, retention tags, redaction state, and access audit.

## Evaluation and scientific claims

The paper proposes evaluation for identity stability, boundary integrity, non-clinical language, backend non-disclosure, anti-dependency behavior, anti-tracker collapse, and continuity usefulness.

Implementation references:

- `relic/eval/harness.py` defines release-gate thresholds and reports.
- `relic/eval/metrics.py` defines metric results and severity metrics.
- `relic/eval/gumi_roleplay.py` evaluates prompt-context completeness and roleplay scenarios.
- `relic/eval/replication_bundle.py` creates replication bundles while excluding raw data.
- `relic/lab/eval_contract.py` blocks runtime-affecting evaluation in lab contracts.
- `fixtures/gumi-eval/` covers identity collapse, clinical collapse, tracker collapse, backend disclosure, label disclosure, and relational recall.
- `fixtures/memory-positive/`, `fixtures/gumi-memory/`, `fixtures/memory-dynamics/`, and `fixtures/gumi-roleplay/` support focused evaluation scenarios.

Tests:

- `tests/eval/`
- `tests/gumi-eval/`
- `tests/gumi_roleplay/`
- `tests/lab/`

Current scientific status:

- The project provides architecture, contracts, fixtures, and evaluation harnesses.
- It does not yet report a full empirical study of participant outcomes.
- It does not claim clinical efficacy, diagnosis, treatment, or validated psychometric measurement.

## Key invariants

| Invariant | Why it matters academically | Code and test evidence |
|---|---|---|
| Safety signals are not memories | Prevents hidden clinical governance from becoming Gumi recall. | `relic/patterns/`, `relic/safety/`, `tests/gumi_continuity/test_sensitive_signal_not_stored_as_continuity_marker.py` |
| Subject words are authoritative for continuity | Preserves negotiated relational memory instead of model authority. | `relic/shared_continuity/service.py`, `tests/shared-continuity/test_subject_words_preserved.py`, `tests/shared-continuity/test_authoritative_correction_recall.py` |
| Blocked context is not injected | Prevents unsafe hidden material from reaching Gumi. | `relic/context_pack/`, `hermes-plugin/tools/relic_shared_continuity/hooks.py`, `tests/hermes_compat/test_plugin_context_pack_ephemeral.py` |
| Delivery requires scope and allowlist | Keeps proactivity governed rather than automatic. | `relic/hermes_runtime.py`, `tests/hermes/test_delivery_gate.py`, `tests/hermes/test_platform_allowlist_contract.py` |
| Runtime output is reviewed | Prevents clinical labels, false lived experience, dependency claims, and backend disclosure. | `relic/gumi_plugin/critic.py`, `tests/gumi_roleplay/`, `tests/gumi_plugin/test_output_sanitizer.py` |
| Workbench panels are separated | Prevents safety-review operations from creating continuity memory or clinical labels. | `relic/ui/workbench_panels.py`, `tests/ui/test_workbench_panel_separation.py` |
| Chronicle is audit truth | Makes governance contestable and reproducible. | `relic/chronicle/`, `tests/chronicle/` |

## What is implemented versus target architecture

| Area | Current status |
|---|---|
| SQLite application database | Current default backend. PostgreSQL is migration target, not runtime default. |
| Chronicle audit ledger | Implemented with SQLite + JSONL, retention, access audit, snapshots, provenance, redaction. |
| Hermes adapter facade | Implemented and tested at facade level; live hook/cron/handoff adoption still deepening. |
| Shared Continuity service | In-process by default; optional injectable SQLite-backed repository (`repository.py` + migration `0013`) gives durable markers/corrections/scope/lifecycle across restart, with tested backup/restore drill. Multi-week live-field durability still unproven. |
| Researcher workbench | Contract and fixture-backed surfaces implemented; live backend/render layer is still alpha/prototype. |
| External memory providers | Hindsight/local is most tested; Byterover/Honcho are evaluation fixtures, not runtime defaults. |
| WhatsApp, Email, SMS | Not implemented delivery adapters in the public alpha. |
| Evaluation | Harnesses, fixtures, and release-gate tests exist; no full deployment study is claimed. |

## Reading guide for reviewers

If you are reviewing the research claim, start with:

1. `relic_gumi_paper_package/manuscript/relic-gumi-manuscript.md`
2. [Theoretical Grounding](theoretical-grounding.md)
3. [Limitations](limitations.md)
4. this document

If you are reviewing the architecture, start with:

1. [Runtime Pipeline](../architecture/pipeline.md)
2. [Data Model](../architecture/data-model.md)
3. [Chronicle](../architecture/chronicle.md)
4. [Privacy Stages](../architecture/privacy-stages.md)
5. [Module Map](../architecture/module-map.md)

If you are reviewing implementation evidence, inspect:

1. `relic/shared_continuity/service.py`
2. `relic/patterns/signal_extractor.py`
3. `relic/hermes_runtime.py`
4. `relic/hermes_adapter/`
5. `relic/chronicle/`
6. `relic/ui/workbench_panels.py`
7. `tests/shared-continuity/`
8. `tests/gumi_continuity/`
9. `tests/hermes/`
10. `tests/hermes_compat/`
11. `tests/ui/`

## Terminology bridge

| Paper term | Codebase term or location |
|---|---|
| Relic | `relic/` package; governance/modeling layer |
| Gumi | `relic/gumi/`, `relic/gumi_plugin/`, Gumi profiles under subject provisioning |
| Hermes | runtime integration through `relic/hermes_runtime.py`, `relic/hermes_adapter/`, `relic/hermes_plugin/`, and `hermes-plugin/` |
| Shared Continuity Memory | `relic/shared_continuity/`, `relic/gumi_continuity/` |
| Continuity marker | `ContinuityMarker` in `relic/shared_continuity/service.py` |
| Safety signal | `relic/patterns/signal_extractor.py`, `relic/safety/` |
| Behavior policy patch | `relic/patterns/policy_compiler.py`, workbench behavior constraint previews |
| PromptContextPack | `relic/context_pack/` |
| Runtime mediation | `relic/hermes_runtime.py`, `relic/hermes_adapter/`, `relic/gumi_plugin/cron_wiring.py` |
| Researcher Workbench | `relic/ui/`, `fixtures/researcher-workbench/`, `tests/ui/` |
| Audit ledger | `relic/chronicle/` |
| Evaluation framework | `relic/eval/`, `relic/lab/`, `fixtures/`, `tests/eval/` |

## Practical limitations for citation or publication

When citing or describing the current artifact, use these constraints:

- Relic/Gumi is research infrastructure, not a clinical system.
- Safety signals are governance signals, not diagnostic findings.
- Shared Continuity memory stores subject-confirmed relational markers; it is not a general vector-memory truth source.
- The current artifact provides architecture, implementation contracts, fixtures, and tests; it does not provide a completed human-subject deployment study.
- The Hermes adapter facade exists, but some live paths still use older direct integration surfaces.
- The researcher workbench is contract- and fixture-backed in the Python artifact; it should not be overstated as a complete live production UI.
- External memory providers and non-Telegram channels must be described by their alpha status in [Release Status](../contributing/release-status.md).

## Summary

The paper contributes a theory of governed relational continuity. The codebase implements that theory as scoped profiles, continuity markers, admission policies, non-clinical safety governance, runtime delivery gates, output critics, workbench separation, Chronicle audit trails, and evaluation fixtures. The strongest current evidence is not a deployment outcome; it is the system's enforceable boundary structure: what can be remembered, what can be shown to Gumi, what researchers can inspect, what delivery can do, and what must remain auditable.
