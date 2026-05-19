# Safety Signals

The signals you see in the review queue are **governance objects**, not clinical findings. This page explains what each tier and category means at the level a researcher needs to triage the queue.

## Hard invariants

- A safety signal is **not** a diagnosis, screening result, clinical risk score, or therapy recommendation.
- A safety signal is **not** a Shared Continuity marker. Continuity stores what the subject confirmed, not hidden governance interpretation.
- Gumi never receives signal family names, tier labels, raw evidence, or researcher notes. Behavior patches reach her label-stripped.
- The subject never sees hidden sensitive labels (`dependency_escalation`, `food_body_control_context`, …).

If you find yourself talking about a signal as if it were a diagnosis, stop and re-read [No Clinicalization](../ethics/no-clinicalization.md).

## Warning tiers

| Tier | Meaning | What Gumi does | What you do |
|---|---|---|---|
| `T0_audit` | Technical or privacy trace, low-impact governance event | No behavior change | Audit-only; appears in chronicle, not in review queue |
| `T1_context` | Single non-crisis context flag or neutral habit | Conservative language only when relevant | Queue for batch review; no external notification |
| `T2_review` | Repeated non-crisis pattern with capped confidence | Label-stripped behavior constraints may apply | Batchable researcher review; notification only if study policy enables it |
| `T3_interruptive` | Repeated/intense non-crisis pattern needing timely review | Reduce proactivity; affected deliveries gated until you act | Interruptive review the same working day |
| `T4_crisis` | Crisis or self-harm language | Crisis protocol immediately, bypass aggregation | Immediate escalation per study policy |

These are **operational levels**, not severity scores. Do not present them to participants, ethics committees, or external audiences as clinical labels.

## Signal categories

| Category | Examples | What it means in practice |
|---|---|---|
| `crisis_self_harm` | crisis or self-harm language | Immediate bypass; no recurrence needed |
| `attachment_dependency_context` | dependency, exclusivity, romantic pressure, distress after non-response | Govern relational boundaries; do not label the subject |
| `food_body_context` | food control, body image distress, repeated control language | Sensitive context, **not** an eating-disorder inference |
| `sleep_context` | repeated sleep/energy difficulty | Conservative support wording; not mood tracking |
| `substance_context` | substance-related coping language | Avoid advice escalation; review if repeated/intense |
| `habit_context` | neutral routines and preferences | Low-tier by default; only subject-confirmed benign habits may become continuity markers |
| `interaction_boundary` | opt-out pressure, backend disclosure pressure, Gumi overreach | Compile to boundary-preserving constraints |
| `health_context` | medical/psychological advice request, pain/fatigue, sensitive mental health context | Avoid clinical advice; redirect to appropriate support |
| `high_stakes_context` | legal or financial requests | Avoid substantive advice; suggest external expertise |
| `privacy_boundary` / `output_safety` | S2 privacy/output warnings | Audit/workbench by default, not urgent escalation |

A category is not the same as a tier. A `food_body_context` signal might be `T1_context` on a single observation and only escalate to `T2_review` after recurrence + intensity criteria are met.

## Habits vs signals

Neutral habits ("I usually have dinner late") are not signals. They may become Shared Continuity if the subject confirms them and they stay non-sensitive.

Food, sleep, substance, and similar patterns become governance signals **only** when the language is repeated, intense, linked to control/distress, or combined with other safety context — and even then they stay researcher-facing and non-clinical.

## How signals reach you

```
turn → signal extractor → tier+category assigned → aggregator (recurrence rules)
   → either drop, queue (T1/T2), interrupt (T3), or escalate (T4)
   → workbench review queue
   → optional notification (escalation contacts, only if configured)
```

A signal that never accumulates recurrence stays in the queue but does not generate a notification. Aggregation rules are in `relic/safety/`.

## In the review queue

Each item shows:

- Tier, category.
- Redacted evidence refs (chronicle event IDs), not raw subject text.
- The aggregation state (single occurrence, N-of-M, time window).
- Suggested behavior patch, if any, with the label stripped.

To inspect raw evidence (researcher-only):

```bash
chronicle query --subject <subject_id> --category safety --limit 20
```

Raw evidence is gated by `reasoning_capture=raw_researcher_only`; it is excluded from any subject-facing export.

## What signals do NOT cause

- They do not become Gumi memories.
- They do not become facets on the subject profile.
- They are excluded from `relic-profile export` and from `chronicle export --subject ...` unless you explicitly include them with a researcher-only flag.
- They do not change SOUL.md.

If you observe a signal modifying any of the above, file a bug — it is a violation of the architecture, not a feature.

## Notification policy

External notification (e.g. emailing an escalation contact) is **off by default**. Enable per study:

```yaml
# $HERMES_HOME/<profile>/plugins.yaml
plugin: gumi-relational
safety:
  escalation_notify: true
  researcher_email: you@example.com
```

Notifications fire only for `T4_crisis` and, if you opt in, `T3_interruptive`. T1 and T2 never notify; they accumulate in the queue.

## Reading list (literature positioning)

- WHO. *Ethics and governance of artificial intelligence for health.* WHO, 2021.
- WHO. *Safe and ethical AI for health.* WHO, 2024.
- NIST. *AI Risk Management Framework (AI RMF 1.0).* NIST, 2023.
- FDA. *Clinical Decision Support Software guidance.* FDA, 2026.
- Digital phenotyping / passive-sensing literature — behavioral traces are proxy signals, not direct measurements.
- Clinical decision support alert literature — tiered alerts and review queues reduce noisy interruption and alert fatigue.

Relic's design follows the tiered-alert and conservative-governance positions in these sources. It does not implement clinical screening.
