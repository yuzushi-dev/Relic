# Safety Warning Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Position warning/safety signals as researcher-facing governance objects for Relic/Gumi, with escalation only when compatible with the blueprint, paper framing, and academic literature.

**Architecture:** Separate `governance signal`, `behavior policy patch`, `continuity marker`, and `audit event`. Non-crisis signals are aggregated across turns before researcher notification; only crisis/self-harm bypass aggregation.

**Tech Stack:** Python runtime Relic/Hermes, JSON Schema, pytest, Markdown docs, researcher workbench UI schemas.

---

## 1. Research And Positioning

Create this document as the implementation plan. The research-heavy taxonomy lives in `docs/research/safety-warning-taxonomy.md`.

The positioning section must establish these invariants:

- Safety signals are researcher-facing governance objects, not memories.
- Sensitive labels must not reach Gumi or the subject.
- Relic/Gumi must not produce diagnosis, clinical screening, clinical risk scores, therapy, or clinical triage.
- Behavior patches are the only path from safety governance to Gumi behavior, and they must be label-stripped.
- Food/body/sleep/substance/habits are non-clinical context flags, with review only when repeated, intense, or combined.
- S2 privacy/output warnings remain audit/workbench items, not urgent escalation.

Sources to cite and use as rationale:

- WHO AI health governance: ethics, human rights, supervision, accountability ([WHO 2021](https://www.who.int/publications/i/item/9789240029200), [WHO 2023](https://www.who.int/news/item/16-05-2023-who-calls-for-safe-and-ethical-ai-for-health)).
- NIST AI RMF: voluntary, rights-preserving, operational risk management ([NIST AI RMF 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)).
- FDA CDS: avoid patient/caregiver-facing functionality that resembles clinical decision support ([FDA CDS Guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software)).
- Digital phenotyping/passive sensing: behavioral signals are proxies, not direct readings of mental states ([Mohr et al. 2020](https://www.nature.com/articles/s41746-020-0251-5), [JAMA Network Open 2025](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2836023)).
- Eating/body tracking: distinguish neutral tracking from potentially sensitive patterns; avoid causal or clinical conclusions ([Body Image 2024](https://www.sciencedirect.com/science/article/pii/S174014452400158X), [Eating Behaviors 2021](https://www.sciencedirect.com/science/article/abs/pii/S1471015321000957), [self-monitoring RCT](https://pmc.ncbi.nlm.nih.gov/articles/PMC6010018/)).
- AI companions: dependency/attachment is a governance area, not a diagnosis ([De Freitas & Cohen](https://www.hbs.edu/ris/Publication%20Files/Unregulated%20Emotional%20Risks_26f75c0a-8d59-4743-a8d2-1189ce8944a5.pdf)).
- Alert fatigue: use tiering, batch review, and auditability to avoid noisy notifications ([CDS alert appropriateness](https://pmc.ncbi.nlm.nih.gov/articles/PMC4052586/), [CDS optimization review](https://pubmed.ncbi.nlm.nih.gov/33186438/)).

## 2. Data Model

Define or update non-clinical enums:

- `SignalCategory`: `crisis_self_harm`, `privacy_boundary`, `output_safety`, `food_body_context`, `sleep_context`, `substance_context`, `attachment_dependency_context`, `habit_context`, `interaction_boundary`.
- `WarningTier`: `T0_audit`, `T1_context`, `T2_review`, `T3_interruptive`, `T4_crisis`.
- `SignalDisposition`: `queued`, `batched`, `reviewed`, `dismissed`, `policy_patch_created`, `notified`, `suppressed_noise`.
- `EvidenceSensitivity`: `redacted_ref_only`, `summary_only`, `internal_snippet_allowed`.

Mandatory separations:

- `SensitiveSignal`: governance object, researcher-facing, not exported to Gumi.
- `BehaviorPolicyPatch`: label-stripped instruction, with no sensitive category label. Example: `reduce persuasive intensity around body/food talk`.
- `ContinuityMarker`: non-sensitive narrative continuity only; safety labels must not propagate into continuity memory.
- `AuditEvent`: redacted accountability log, no raw text.

Update schemas and docs with backward compatibility for existing signals.

## 3. Runtime

Change runtime semantics without clinical framing:

- Keep crisis/self-harm as immediate bypass: urgent notification, redaction, audit.
- For non-crisis signals, introduce a multi-turn aggregation window before `notify_escalation`.
- Do not notify on a single non-crisis event, even if local confidence crosses a threshold.
- Preserve confidence caps:
  - single event: max `0.30`
  - two events: max `0.55`
  - three or more events: max `0.75`
- Apply thresholds to tiers, not diagnoses:
  - `T0`: technical log/audit.
  - `T1`: context flag in queue, no notification.
  - `T2`: batchable review.
  - `T3`: interruptive review only for repeated/intense patterns with sufficient evidence.
  - `T4`: immediate crisis escalation.
- Food/body/sleep/substance/attachment: review on repeated patterns; escalation only when intensity, recency, and recurrence cross the study policy.
- S2 privacy/output: audit/workbench by default; urgent notification only if combined with material leakage or a defined operational risk.
- All notifications must use redacted evidence refs, never raw text.

### Hermes Runtime Constraints

This implementation must conform to the Hermes hook model:

- Use plugin hooks for CLI + gateway coverage. Gateway event hooks under `~/.hermes/hooks/` are gateway-only and should not be the primary runtime path.
- Hook callbacks must accept `**kwargs` for forward compatibility with future Hermes parameters.
- `pre_llm_call` fires once per user turn before the tool loop. Its return value can inject context, but injected context is appended to the current user message, not the system prompt, and is ephemeral.
- Safety scans that only observe or audit should return `None` so they do not inject anything into the turn.
- If a behavior policy patch is injected through `pre_llm_call`, it must be label-stripped and must not contain signal family names, raw evidence, or researcher-only notes.
- Do not rely on mutating `conversation_history`; Hermes does not persist `pre_llm_call` injected context into the session database.
- `post_llm_call` is observer-only and fires only after successful, non-interrupted turns. Critical crisis detection must stay in `pre_llm_call` or an earlier gateway dispatch layer, not only in `post_llm_call`.
- `transform_llm_output` may replace the final response text. Use it for final-output language safety, not for storing safety signals or sending researcher notifications.
- Hooks are best-effort: errors are caught/logged by Hermes and must not be the only durable record of a safety event. Relic must write its own redacted audit/Chronicle event before or alongside any external notification.
- Hermes persistent memory (`MEMORY.md`, `USER.md`) is loaded into the system prompt at session start and is not the place for safety signals. Add tests that safety signals, warning tiers, and researcher-only notes are never written into Hermes memory providers or project context files.
- If Relic is loaded as a project-local Hermes plugin, deployment docs must state that Hermes disables project-local plugins by default unless `HERMES_ENABLE_PROJECT_PLUGINS=true` is set for trusted repositories.

## 4. UI / Workbench

Researcher-facing workbench requirements:

- Queue filters for `WarningTier`, `SignalCategory`, `SignalDisposition`, recency, and source.
- Clear distinction between `batchable` and `interruptive`.
- Redacted evidence refs: turn id/hash, timestamp, detector family, capped confidence, short rationale.
- Actions:
  - `mark reviewed`
  - `dismiss as noise`
  - `create label-stripped behavior patch`
  - `escalate researcher notification`
  - `suppress repeated duplicate`
- No subject-visible UI for safety labels.
- No sensitive label sent to Gumi.
- Audit trail for every human review decision.

## 5. Tests

Write tests before implementation:

- Contract tests for JSON schemas: new enums, required fields, raw text forbidden.
- Unit tests for `relic/patterns/signal_extractor.py`: caps, category mapping, crisis bypass, neutral habit vs sensitive repeated pattern.
- Runtime tests for Hermes hooks: single non-crisis event does not notify; two/three events aggregate; crisis notifies immediately.
- Regression tests for privacy: S2 remains audit/workbench, not urgent escalation.
- UI schema tests: queue supports tier/disposition/redacted evidence.
- Eval gates: food/body/habit/behavior fixtures with non-diagnostic language.
- Negative tests: no diagnosis, no clinical score, no sensitive label in continuity or behavior patches.

## 6. Likely Files

- Modify: `relic/patterns/signal_extractor.py`
- Modify: `hermes-plugin/tools/relic_shared_continuity/hooks.py`
- Modify: `hermes-plugin/tools/relic_shared_continuity/hooks_adapter.py`
- Modify: `relic/safety/escalation_notifier.py`
- Modify: `relic/privacy_gate.py`
- Modify: `schemas/data-model/sensitive_signal.schema.json`
- Modify: `schemas/ui/safety_signal_panel.schema.json`
- Modify: `docs/ethics/index.md`
- Modify: `docs/ethics/boundaries.md`
- Modify: `docs/architecture/data-model.md`
- Modify: `relic_gumi_paper_package/manuscript/relic-gumi-manuscript.md`
- Modify: `tests/patterns/*`
- Modify: `tests/safety/*`
- Modify: `tests/ui/*`
- Create: `docs/research/safety-warning-taxonomy.md` if the literature matrix becomes too large for this plan.

## 7. Risks And Open Questions

Main risks:

- Over-alerting: mitigate with batch review, deduplication, and multi-turn thresholds.
- Clinical drift: forbid diagnostic names, clinical scores, and treatment suggestions.
- Label leakage: test every path into Gumi, continuity, export, and subject-visible UI.
- False confidence: document that signals are behavioral proxies.
- Eating/body overreach: treat neutral tracking as habit unless repeated/intense sensitive patterns emerge.
- Privacy leakage: redacted evidence refs and summaries by default.

Open questions:

- Which aggregation window should be used: turn count, wall-clock time, or session boundary?
- Who are the reviewers, and what SLA applies to `T2` and `T3`?
- Should `T3` always send email, or only when configured in `delivery_policy.json`?
- Should behavior patches persist or expire after review/session?
- Is an explicit allowlist needed for categories that may generate label-stripped behavior patches?
